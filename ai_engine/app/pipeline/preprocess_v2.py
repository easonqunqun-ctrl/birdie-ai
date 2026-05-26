"""P2-M7-02 · 视频读取增强 V2（**与 V1 并存，opt-in**）。

设计契约（kickoff §1.2 / §2 / §10.3）
------------------------------------
- **V1 行为冻结**：`preprocess.py::preprocess_video` 默认入口不动，老用户/老调用方继续走
  30fps / 720p / yuv420p / H.264。
- **V2 入口**：`preprocess_video_v2`；ai_engine main.py 仅在 `engine_version == "v2"` 桶且
  `M7_VIDEO_READER_V2_ENABLED=true` 时切换调用，灰度框架走 P2-M7-14。
- 新增能力：
  * FR-1 HEVC / VP9 容器识别（ffprobe 读 codec_name + container_format_name）
  * FR-2 24/30/60/120/240 fps → 统一 **60fps** 时间轴（慢动作走 nominal_fps）
  * FR-3 10-bit HDR → sRGB（zscale tonemap 链 hable）
  * FR-4 慢动作元数据（mov edit list + tags）
  * FR-5 短边 720 / 1080 分层（按 docs/05 §2.2 设备矩阵决策）
  * FR-6 音频通道保留（供 M8 教练语音批注对齐）
- 错误码新增：`DecodeError(50120)`（codec 不被支持）；50101 保留给下载 / 容器损坏

为什么独立文件
--------------
V1 仍是一期黄金路径，本周期内业务流量 80% 走 V1。把 V2 拆到独立模块：
1. 单元测试可以分别 freeze V1 行为 & 演进 V2 行为
2. 灰度回滚只需切 router，不需要 git revert
3. 文件膨胀控制：V1 (660 行) + V2 (本文件) 比单一 1200 行文件易读
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.errors import DecodeError, PreprocessError
from app.pipeline.engine_warnings import EngineWarning
from app.pipeline.preprocess import (
    MAX_DURATION_SEC,
    MAX_FRAME_LOSS_RATIO,
    MIN_CLARITY_SCORE,
    MIN_DURATION_SEC,
    PreprocessResult,
    _materialize_input,
    _require_binary,
    _scan_quality,
    composite_quality_score,
    enforce_quality_gates,
)

# ============================================================
# V2 归一化目标（kickoff §2.4）
# ============================================================

TARGET_FPS_V2 = 60  # vs V1 的 30
TARGET_SHORT_SIDE_V2_DEFAULT = 720  # 老机型
TARGET_SHORT_SIDE_V2_FLAGSHIP = 1080  # 旗舰机型（docs/05 §2.2 矩阵就位后切换）
TARGET_VCODEC_V2 = "libx264"
TARGET_PIX_FMT_V2 = "yuv420p"
TARGET_ACODEC_V2 = "aac"  # FR-6：M8 教练语音批注用
TARGET_ABITRATE_V2 = "64k"

# 受支持容器/codec 白名单（kickoff §2.4 FR-1）
SUPPORTED_CODECS: frozenset[str] = frozenset(
    {
        "h264",
        "hevc",
        "h265",
        "vp9",
        "vp8",
        "av1",
        "mpeg4",
    }
)

SUPPORTED_CONTAINERS: frozenset[str] = frozenset(
    {
        "mov,mp4,m4a,3gp,3g2,mj2",
        "matroska,webm",
        "mp4",
        "mov",
        "webm",
    }
)


# ============================================================
# 扩展数据结构
# ============================================================


@dataclass
class _ProbeInfoExtended:
    """V2 扩展 ffprobe 输出（kickoff §2.4 FR-1 / FR-4）。

    与 V1 `_ProbeInfo` 兼容（前 4 字段对齐），新增 codec / 色彩管线 / 慢动作字段。
    """

    duration_sec: float
    width: int
    height: int
    fps_raw: float
    codec_name: str = ""  # h264 / hevc / vp9 / ...
    container_format_name: str = ""  # mov,mp4,m4a,3gp,3g2,mj2 / matroska,webm
    pix_fmt: str = ""  # yuv420p / yuv420p10le / ...
    color_space: str = ""  # bt709 / bt2020nc / ...
    color_transfer: str = ""  # bt709 / smpte2084 / ...
    color_primaries: str = ""
    has_audio: bool = False
    nominal_fps: float = 0.0  # mov 容器 nominal frame rate；区分慢动作
    is_slowmo: bool = False  # nominal_fps > fps_raw 显著
    is_hdr: bool = False  # color_transfer in {smpte2084, arib-std-b67}
    is_10bit: bool = False  # pix_fmt 含 10le


@dataclass
class PreprocessResultV2(PreprocessResult):
    """V2 预处理产物。继承 V1 全部字段，扩展 codec / 色彩 / 慢动作元数据。"""

    codec_name: str = ""
    pix_fmt_input: str = ""
    is_hdr_input: bool = False
    nominal_fps: float = 0.0
    is_slowmo: bool = False
    has_audio: bool = False
    engine_version: Literal["v1", "v2"] = "v2"
    engine_warnings: list[EngineWarning] = field(default_factory=list)


# ============================================================
# 主入口（V2）
# ============================================================


def preprocess_video_v2(
    input_path_or_url: str,
    *,
    work_dir: Path | None = None,
    min_clarity: float = MIN_CLARITY_SCORE,
    max_frame_loss: float = MAX_FRAME_LOSS_RATIO,
    min_duration: float = MIN_DURATION_SEC,
    max_duration: float = MAX_DURATION_SEC,
    target_short_side: int = TARGET_SHORT_SIDE_V2_DEFAULT,
) -> PreprocessResultV2:
    """V2 视频读取主入口。

    与 V1 差异：
    - TARGET_FPS = 60（V1 = 30）
    - 慢动作走 nominal_fps 还原真实时间轴
    - HEVC / VP9 自动解码；HDR → sRGB tonemap
    - 音频保留（FR-6）
    - 失败抛 `DecodeError(50120)` 而非 `PreprocessError(50101)`（codec 不支持时）

    Raises:
        PreprocessError(50101): 下载失败 / 容器损坏 / 时长越界
        DecodeError(50120): codec 不支持 / tonemap 失败 / pix_fmt 转换失败
        PoorQualityError(50102): 清晰度 / 稳定度 / 帧丢失不达标
    """
    work_dir = work_dir or Path(tempfile.mkdtemp(prefix="ai_engine_preproc_v2_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    engine_warnings: list[EngineWarning] = []

    source_path = _materialize_input(input_path_or_url, work_dir)

    probe = _ffprobe_extended(source_path)
    _validate_duration(probe, min_duration=min_duration, max_duration=max_duration)
    _validate_codec(probe, engine_warnings)

    if probe.is_slowmo and probe.nominal_fps > 0:
        engine_warnings.append(
            EngineWarning(
                code="slowmo_detected",
                level="info",
                detail=f"nominal_fps={probe.nominal_fps:.1f} vs fps_raw={probe.fps_raw:.1f}",
            )
        )
        engine_warnings.append(
            EngineWarning(
                code="nominal_fps_used",
                level="info",
                detail=f"using nominal_fps={probe.nominal_fps:.1f} for timeline normalization",
            )
        )

    if probe.is_hdr:
        engine_warnings.append(
            EngineWarning(
                code="hdr_tonemapped",
                level="info",
                detail=f"color_transfer={probe.color_transfer} → bt709 via zscale/hable",
            )
        )

    if probe.codec_name in {"hevc", "h265"}:
        engine_warnings.append(
            EngineWarning(code="decoded_hevc", level="info", detail=f"codec={probe.codec_name}")
        )
    elif probe.codec_name == "vp9":
        engine_warnings.append(
            EngineWarning(code="decoded_vp9", level="info", detail="codec=vp9")
        )

    if probe.fps_raw > 0 and probe.fps_raw != TARGET_FPS_V2:
        code = "fps_upsampled" if probe.fps_raw < TARGET_FPS_V2 else "fps_downsampled"
        engine_warnings.append(
            EngineWarning(
                code=code,
                level="info",
                detail=f"{probe.fps_raw:.1f}fps → {TARGET_FPS_V2}fps",
            )
        )

    normalized_path = work_dir / "normalized.mp4"
    _ffmpeg_normalize_v2(
        source_path,
        normalized_path,
        probe,
        target_short_side=target_short_side,
        engine_warnings=engine_warnings,
    )

    if probe.has_audio:
        engine_warnings.append(EngineWarning(code="audio_kept", level="info", detail=f"acodec={TARGET_ACODEC_V2}"))
    else:
        engine_warnings.append(EngineWarning(code="audio_dropped", level="info", detail="source has no audio stream"))

    stats = _scan_quality(normalized_path)

    quality_score = composite_quality_score(
        stats,
        min_clarity=min_clarity,
        max_frame_loss=max_frame_loss,
    )

    result = PreprocessResultV2(
        normalized_video_path=normalized_path,
        fps=stats.fps,
        num_frames=stats.num_frames,
        width=stats.width,
        height=stats.height,
        duration_sec=stats.num_frames / stats.fps if stats.fps > 0 else 0.0,
        clarity_score=stats.clarity_score,
        stability_score=stats.stability_score,
        frame_loss_ratio=stats.frame_loss_ratio,
        quality_score=quality_score,
        low_clarity_frame_ratio=stats.low_clarity_frame_ratio,
        codec_name=probe.codec_name,
        pix_fmt_input=probe.pix_fmt,
        is_hdr_input=probe.is_hdr,
        nominal_fps=probe.nominal_fps,
        is_slowmo=probe.is_slowmo,
        has_audio=probe.has_audio,
        engine_version="v2",
        engine_warnings=engine_warnings,
    )

    enforce_quality_gates(
        stats,
        min_clarity=min_clarity,
        max_frame_loss=max_frame_loss,
    )

    return result


# ============================================================
# 内部：扩展 ffprobe（FR-1 / FR-3 / FR-4）
# ============================================================


def _ffprobe_extended(video_path: Path) -> _ProbeInfoExtended:
    """V2 扩展 ffprobe，读 codec / pix_fmt / color_space / nominal_fps。

    比 V1 `_ffprobe` 多读 4 类字段：
    1. `codec_name` + `format_name`：判断容器/codec 是否支持
    2. `pix_fmt`：判断 8-bit / 10-bit
    3. `color_space` / `color_transfer` / `color_primaries`：判断 HDR
    4. `tags:com.apple.quicktime.live-photo.auto`（mov）或 `nb_frames`（mp4）反推 nominal_fps
    """
    _require_binary("ffprobe")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-print_format",
        "json",
        str(video_path),
    ]
    try:
        out = subprocess.run(cmd, check=True, capture_output=True, timeout=15).stdout.decode("utf-8")
    except subprocess.CalledProcessError as exc:
        raise PreprocessError(
            f"ffprobe 读取失败 (exit={exc.returncode}): {exc.stderr.decode('utf-8', errors='ignore')[:200]}",
            user_message="视频文件损坏，请重新上传",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PreprocessError("ffprobe 超时（>15s），视频可能损坏") from exc

    return _parse_ffprobe_json(out)


def _parse_ffprobe_json(json_text: str) -> _ProbeInfoExtended:
    """把 ffprobe JSON 输出解析成 `_ProbeInfoExtended`。

    独立函数以便单测用 fixture JSON 直接喂入，不必构造真实视频。
    """
    import json as _json

    try:
        data = _json.loads(json_text)
    except _json.JSONDecodeError as exc:
        raise PreprocessError(f"ffprobe 输出非 JSON: {exc}") from exc

    fmt = data.get("format", {})
    streams = data.get("streams", []) or []

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not v_stream:
        raise PreprocessError("ffprobe 未找到视频流", user_message="视频文件无视频流，请重新上传")

    try:
        width = int(v_stream.get("width", 0))
        height = int(v_stream.get("height", 0))
        codec_name = (v_stream.get("codec_name") or "").lower()
        pix_fmt = (v_stream.get("pix_fmt") or "").lower()
        color_space = (v_stream.get("color_space") or "").lower()
        color_transfer = (v_stream.get("color_transfer") or "").lower()
        color_primaries = (v_stream.get("color_primaries") or "").lower()
        duration = float(fmt.get("duration", "0") or 0)
        container_format_name = (fmt.get("format_name") or "").lower()

        r_fr = v_stream.get("r_frame_rate", "0/1") or "0/1"
        num, den = r_fr.split("/")
        fps_raw = float(num) / float(den) if float(den) > 0 else 0.0
    except (KeyError, ValueError, TypeError) as exc:
        raise PreprocessError(f"ffprobe JSON 解析失败: {exc}") from exc

    nominal_fps = _extract_nominal_fps(v_stream, fmt) or 0.0
    is_slowmo = bool(nominal_fps > 0 and fps_raw > 0 and nominal_fps + 5.0 < fps_raw)

    is_hdr = color_transfer in {"smpte2084", "arib-std-b67"}
    is_10bit = "10le" in pix_fmt or "p010" in pix_fmt

    return _ProbeInfoExtended(
        duration_sec=duration,
        width=width,
        height=height,
        fps_raw=fps_raw,
        codec_name=codec_name,
        container_format_name=container_format_name,
        pix_fmt=pix_fmt,
        color_space=color_space,
        color_transfer=color_transfer,
        color_primaries=color_primaries,
        has_audio=a_stream is not None,
        nominal_fps=nominal_fps,
        is_slowmo=is_slowmo,
        is_hdr=is_hdr,
        is_10bit=is_10bit,
    )


def _extract_nominal_fps(v_stream: dict, fmt: dict) -> float:
    """从 ffprobe stream/format tags 里反推 nominal_fps（mov edit list）。

    iPhone 240fps 慢动作真实时间轴是 30fps，但 r_frame_rate 报 240。
    mov 容器在 `tags:com.apple.quicktime.live-photo.auto` 或 stream `tags:nominal_frame_rate`
    或 mp4 `tags:nominal_frame_rate` 里会标记真实帧率。
    """
    tags = (v_stream.get("tags") or {})
    for key in ("nominal_frame_rate", "com.apple.quicktime.capture.fps", "NOMINAL_FRAME_RATE"):
        if key in tags:
            try:
                return float(tags[key])
            except (ValueError, TypeError):
                continue
    fmt_tags = fmt.get("tags") or {}
    for key in ("nominal_frame_rate", "com.apple.quicktime.live-photo.auto"):
        if key in fmt_tags:
            try:
                return float(fmt_tags[key])
            except (ValueError, TypeError):
                continue
    return 0.0


def _validate_duration(probe: _ProbeInfoExtended, *, min_duration: float, max_duration: float) -> None:
    if probe.duration_sec < min_duration:
        raise PreprocessError(
            f"视频时长 {probe.duration_sec:.1f}s 不足 {min_duration}s",
            user_message=f"视频时长过短（至少需要 {int(min_duration)} 秒）",
        )
    if probe.duration_sec > max_duration:
        raise PreprocessError(
            f"视频时长 {probe.duration_sec:.1f}s 超过 {max_duration}s",
            user_message=f"视频时长过长（最多 {int(max_duration)} 秒）",
        )


def _validate_codec(probe: _ProbeInfoExtended, engine_warnings: list[EngineWarning]) -> None:
    """codec 不在白名单 → 抛 50120 DecodeError。"""
    if not probe.codec_name:
        raise DecodeError(
            "ffprobe 未识别出 codec_name",
            user_message="视频编码格式无法识别，请使用 H.264 / mp4 格式",
        )
    if probe.codec_name not in SUPPORTED_CODECS:
        raise DecodeError(
            f"codec={probe.codec_name} 不在 V2 镜像支持白名单 {sorted(SUPPORTED_CODECS)}",
            user_message="视频格式暂不支持，请使用 H.264 / mp4 格式重新拍摄",
        )


# ============================================================
# 内部：V2 ffmpeg 归一化（FR-2 / FR-3 / FR-6）
# ============================================================


def _ffmpeg_normalize_v2(
    source: Path,
    dest: Path,
    probe: _ProbeInfoExtended,
    *,
    target_short_side: int,
    engine_warnings: list[EngineWarning],
) -> None:
    """V2 ffmpeg 归一化：60fps / yuv420p / HDR tonemap / 音频保留。

    filter 链构造（按 probe 内容动态拼）：
    - 短边缩放（V1 复用同样的 even-pixel 处理）
    - HDR → zscale tonemap hable → bt709
    - 慢动作时间轴还原：`setpts=PTS*nominal_fps/fps_raw`
    - 最终 `-r {TARGET_FPS_V2}` + `-pix_fmt yuv420p`
    """
    _require_binary("ffmpeg")

    if min(probe.width, probe.height) <= target_short_side:
        scale_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    elif probe.width < probe.height:
        scale_filter = f"scale={target_short_side}:-2"
    else:
        scale_filter = f"scale=-2:{target_short_side}"

    vf_parts: list[str] = [scale_filter]

    if probe.is_hdr or probe.is_10bit:
        vf_parts.append(
            "zscale=t=linear:npl=100,format=gbrpf32le,"
            "zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
            "zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
        )

    if probe.is_slowmo and probe.nominal_fps > 0 and probe.fps_raw > 0:
        slowmo_ratio = probe.nominal_fps / probe.fps_raw
        vf_parts.append(f"setpts=PTS*{1.0 / slowmo_ratio:.6f}")

    vf_chain = ",".join(vf_parts)

    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        vf_chain,
        "-r",
        str(TARGET_FPS_V2),
        "-c:v",
        TARGET_VCODEC_V2,
        "-pix_fmt",
        TARGET_PIX_FMT_V2,
        "-preset",
        "veryfast",
        "-crf",
        "23",
    ]

    if probe.has_audio:
        cmd += ["-c:a", TARGET_ACODEC_V2, "-b:a", TARGET_ABITRATE_V2]
    else:
        cmd += ["-an"]

    cmd += [
        "-movflags",
        "+faststart",
        str(dest),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="ignore")[:300]
        if _is_codec_failure(stderr):
            raise DecodeError(
                f"ffmpeg v2 codec/tonemap 转码失败 (exit={exc.returncode}): {stderr}",
                user_message="视频格式暂不支持，请使用 H.264 / mp4 格式重新拍摄",
            ) from exc
        raise PreprocessError(
            f"ffmpeg v2 转码失败 (exit={exc.returncode}): {stderr}",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PreprocessError("ffmpeg v2 转码超时（>180s）") from exc

    if not dest.exists() or dest.stat().st_size == 0:
        raise PreprocessError("ffmpeg v2 输出文件为空")

    if vf_chain:
        engine_warnings.append(
            EngineWarning(
                code="color_space_normalized",
                level="info",
                detail=f"vf chain: {vf_chain[:120]}",
            )
        )


_CODEC_FAILURE_KEYWORDS: tuple[str, ...] = (
    "decoder not found",
    "no such filter",
    "encoder not found",
    "unknown encoder",
    "unknown decoder",
    "unsupported codec",
    "could not find tag",
    "zscale",
    "tonemap",
    "libzimg",
    "libx265",
    "libvpx",
)


def _is_codec_failure(stderr_text: str) -> bool:
    """简单关键字判断 stderr 是否属于 codec/tonemap 类失败 → 走 50120。"""
    low = stderr_text.lower()
    return any(kw in low for kw in _CODEC_FAILURE_KEYWORDS)
