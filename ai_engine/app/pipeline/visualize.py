"""W6-T3：把 T1-T2 的姿态/分段产物可视化并落盘。

三个产物
--------
1. **骨骼叠加视频**：在 normalized 视频每帧上画 33 个 landmark + MediaPipe
   `POSE_CONNECTIONS` 连线，用 ffmpeg 编码成 H.264 mp4（保证浏览器/微信能播）
2. **关键帧图**：按 issue 的 `key_frame_timestamp` 抽帧 → JPG（quality=85）
3. **骨骼时序 parquet**：把 (F, 33, 3) + visibility 写成 parquet，
   方便前端 mini-cdn 拉取做"骨骼回放"功能

为什么用 ffmpeg 子进程而不是 cv2.VideoWriter
-----------------------------------------
- cv2.VideoWriter 用 `mp4v` fourcc 输出的是 **MPEG-4 Part 2**，iOS Safari /
  WeChat WebView 普遍不支持
- 用 `avc1` fourcc 需要 OpenCV 编译时带 H.264 支持，headless wheel 不带
- 最稳妥：把每帧 BGR 数据通过 stdin 喂给 ffmpeg `libx264 -pix_fmt yuv420p`，
  跨平台 100% 兼容
- ffmpeg 在 W6-T1 装包步骤已经进 Dockerfile，免得再加依赖

性能预算
-------
- 骨骼视频：90 帧 @ 720p × （drawing ~1ms/frame + ffmpeg 编码 30fps real-time）
  ≈ 3-4s
- 关键帧 JPG：每张 < 100ms
- parquet：< 200ms
- T3 总耗时预算 < 8s（docs/14 §5）
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from app.pipeline.diagnose import DiagnosedIssue
    from app.pipeline.pose import PoseResult

log = logging.getLogger("ai_engine.visualize")

# O-07：微信小程序 / WebView 流畅播放下限（docs/01 §4.3）
MIN_SKELETON_PLAYBACK_FPS = 24.0
# 与 preprocess 归一化目标一致
DEFAULT_SKELETON_OUTPUT_FPS = 30.0

# 绘制风格（统一一份，便于调）
_LANDMARK_COLOR = (0, 255, 0)  # BGR：绿色 = 关键点
_CONNECTION_COLOR = (0, 200, 255)  # BGR：橙色 = 骨骼连线
_LANDMARK_RADIUS = 4
_CONNECTION_THICKNESS = 2
_VISIBILITY_THRESHOLD = 0.5  # 单关键点低于这个阈值就不画

# JPG 质量（OpenCV 默认 95；85 体积小一半、肉眼几乎无差）
_JPEG_QUALITY = 85


# ============================================================
# 数据结构
# ============================================================


@dataclass
class VisualizeArtifacts:
    """三类衍生产物的本地路径（上传成功后由 storage 把它们换成 URL）。

    Attributes:
        skeleton_video_path: 骨骼叠加视频本地路径，None 表示生成失败/跳过
        keyframes_paths: {issue_type: jpg_path}；仅包含成功抽帧的
        pose_data_path: parquet 本地路径
    """

    skeleton_video_path: Path | None
    keyframes_paths: dict[str, Path]
    pose_data_path: Path | None


@dataclass(frozen=True)
class VideoStreamProbe:
    """ffprobe 抽样的视频流信息（用于 O-07 FPS 验收）。"""

    fps: float
    frame_count: int | None
    codec: str | None


def parse_ffprobe_fps(raw: str) -> float:
    """解析 ffprobe `avg_frame_rate` / `r_frame_rate`（如 `30000/1001`）。"""
    text = (raw or "").strip()
    if not text or text == "0/0":
        return 0.0
    if "/" in text:
        num, den = text.split("/", 1)
        den_f = float(den)
        if den_f <= 0:
            return 0.0
        return float(num) / den_f
    try:
        return float(text)
    except ValueError:
        return 0.0


def resolve_skeleton_output_fps(
    *,
    container_fps: float | None,
    pose_fps: float | None,
) -> float:
    """决定骨骼叠加 mp4 的编码帧率；保证 ≥ MIN_SKELETON_PLAYBACK_FPS。"""
    candidate = container_fps if container_fps and container_fps > 0 else None
    if candidate is None and pose_fps and pose_fps > 0:
        candidate = float(pose_fps)
    if candidate is None or candidate <= 0:
        candidate = DEFAULT_SKELETON_OUTPUT_FPS

    if candidate < MIN_SKELETON_PLAYBACK_FPS:
        return MIN_SKELETON_PLAYBACK_FPS
    # 归一化管线目标 30fps；接近 30 时对齐，避免 29.97 漂移
    if candidate >= 28.0:
        return DEFAULT_SKELETON_OUTPUT_FPS
    return float(candidate)


def probe_video_stream(path: Path | str) -> VideoStreamProbe | None:
    """用 ffprobe 读取视频流 fps / 帧数 / 编码；失败返回 None。"""
    target = Path(path)
    if not target.exists():
        return None
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=avg_frame_rate,nb_frames,codec_name",
        "-of",
        "json",
        str(target),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        import json

        payload = json.loads(proc.stdout or "{}")
        streams = payload.get("streams") or []
        if not streams:
            return None
        stream = streams[0]
        fps = parse_ffprobe_fps(str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or ""))
        nb_raw = stream.get("nb_frames")
        frame_count = int(nb_raw) if nb_raw not in (None, "N/A") else None
        codec = stream.get("codec_name")
        return VideoStreamProbe(fps=fps, frame_count=frame_count, codec=str(codec) if codec else None)
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def skeleton_playback_fps_ok(probe: VideoStreamProbe | None) -> bool:
    if probe is None or probe.fps <= 0:
        return False
    return probe.fps + 1e-3 >= MIN_SKELETON_PLAYBACK_FPS


# ============================================================
# 1. 骨骼叠加视频
# ============================================================


def _pose_connections() -> list[tuple[int, int]]:
    """MediaPipe 自带的 POSE_CONNECTIONS（35 条边）。

    放在函数里延迟 import：mediapipe 导入约 1.5s，不应在模块顶部 import。
    """
    import mediapipe as mp

    return list(mp.solutions.pose.POSE_CONNECTIONS)


def _draw_pose_on_frame(
    frame: np.ndarray,
    keypoints_xy: np.ndarray,
    visibility: np.ndarray,
    connections: list[tuple[int, int]],
) -> np.ndarray:
    """在单帧上画骨骼。

    Args:
        frame: BGR 图像，shape=(H, W, 3)
        keypoints_xy: shape=(33, 2)；归一化坐标 [0,1]
        visibility: shape=(33,)；< _VISIBILITY_THRESHOLD 的点不画
        connections: list of (idx_a, idx_b)

    Returns:
        修改后的 frame（in-place 操作 + 返回引用）
    """
    import cv2

    h, w = frame.shape[:2]
    pixel_xy = (keypoints_xy * np.array([w, h])).astype(np.int32)

    # 先画连线（这样关键点在最上层，看着舒服）
    for a, b in connections:
        if visibility[a] < _VISIBILITY_THRESHOLD or visibility[b] < _VISIBILITY_THRESHOLD:
            continue
        cv2.line(frame, tuple(pixel_xy[a]), tuple(pixel_xy[b]), _CONNECTION_COLOR, _CONNECTION_THICKNESS)

    for i in range(len(keypoints_xy)):
        if visibility[i] < _VISIBILITY_THRESHOLD:
            continue
        cv2.circle(frame, tuple(pixel_xy[i]), _LANDMARK_RADIUS, _LANDMARK_COLOR, -1)

    return frame


def render_skeleton_video(
    normalized_video_path: Path | str,
    pose_result: PoseResult,
    output_path: Path | str,
) -> Path | None:
    """读 normalized 视频，每帧叠加骨骼，重新编码成 H.264 mp4。

    Args:
        normalized_video_path: T1 preprocess 输出的归一化视频
        pose_result: T1 pose 输出，keypoints/visibility 必须帧数与视频对齐
        output_path: 目标 mp4 路径

    Returns:
        output_path 成功 / None 失败（log 一条 warning，不抛错）
    """
    try:
        import cv2
    except ImportError:  # pragma: no cover
        log.warning("opencv_unavailable")
        return None

    normalized_video_path = Path(normalized_video_path)
    output_path = Path(output_path)
    if not normalized_video_path.exists():
        log.warning("normalized_video_missing", extra={"path": str(normalized_video_path)})
        return None

    cap = cv2.VideoCapture(str(normalized_video_path))
    if not cap.isOpened():
        log.warning("cv2_open_failed", extra={"path": str(normalized_video_path)})
        return None

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    container_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    output_fps = resolve_skeleton_output_fps(
        container_fps=container_fps if container_fps > 0 else None,
        pose_fps=pose_result.fps,
    )

    if width <= 0 or height <= 0:
        cap.release()
        log.warning("cv2_invalid_resolution", extra={"width": width, "height": height})
        return None

    try:
        connections = _pose_connections()
    except Exception as exc:
        cap.release()
        log.warning("pose_connections_unavailable", extra={"error": str(exc)})
        return None

    # ffmpeg 子进程：从 stdin 吃 raw BGR24 → libx264 yuv420p mp4
    # `-vf "pad..."` 让宽高都成偶数（libx264 要求），用 BGR 反推时偶尔会差 1 像素
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{width}x{height}",
        "-r", f"{output_fps:.3f}",
        "-i", "-",
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-c:v", "libx264",
        "-preset", "veryfast",  # MVP：编码速度优先（CPU<3s）
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",  # 网页/小程序可流式播放
        str(output_path),
    ]

    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        frame_idx = 0
        keypoints = pose_result.keypoints  # (F, 33, 3)
        visibility = pose_result.visibility  # (F, 33)
        num_pose_frames = keypoints.shape[0]

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx < num_pose_frames:
                _draw_pose_on_frame(
                    frame,
                    keypoints[frame_idx, :, :2],
                    visibility[frame_idx],
                    connections,
                )
            # 帧数对不上时（pose 比 video 短）：后面几帧不画骨骼但仍写进视频，
            # 不让用户看到时长变化
            assert proc.stdin is not None
            try:
                proc.stdin.write(frame.tobytes())
            except BrokenPipeError:
                # ffmpeg 已退出（编码失败），下一步 wait + stderr 会拿到原因
                break
            frame_idx += 1

        if proc.stdin:
            proc.stdin.close()
        rc = proc.wait(timeout=60)
        if rc != 0:
            stderr = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
            log.warning("ffmpeg_encode_failed", extra={"rc": rc, "stderr": stderr[-500:]})
            return None

        probe = probe_video_stream(output_path)
        if not skeleton_playback_fps_ok(probe):
            log.warning(
                "skeleton_fps_below_min",
                extra={
                    "output": str(output_path),
                    "probed_fps": probe.fps if probe else None,
                    "min_fps": MIN_SKELETON_PLAYBACK_FPS,
                    "encoded_fps": output_fps,
                },
            )
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

        log.info(
            "skeleton_video_rendered",
            extra={
                "output": str(output_path),
                "frames": frame_idx,
                "encoded_fps": output_fps,
                "probed_fps": probe.fps if probe else None,
                "size_bytes": output_path.stat().st_size if output_path.exists() else 0,
            },
        )
        return output_path
    except Exception as exc:
        log.warning("skeleton_render_unknown_error", extra={"error": str(exc)})
        if proc is not None:
            proc.kill()
            proc.wait()
        return None
    finally:
        cap.release()


# ============================================================
# 2. 关键帧 JPG
# ============================================================


def extract_keyframe(
    normalized_video_path: Path | str,
    frame_idx: int,
    output_path: Path | str,
    *,
    pose_result: PoseResult | None = None,
    overlay_pose: bool = True,
) -> Path | None:
    """抽某一帧并存为 JPG（可选叠加骨骼，方便前端 issue 卡片图直观）。

    Args:
        normalized_video_path: 输入视频
        frame_idx: 0-based 帧号
        output_path: 目标 jpg 路径
        pose_result: 提供则可叠加骨骼
        overlay_pose: 是否画骨骼

    Returns:
        output_path 成功 / None 失败
    """
    try:
        import cv2
    except ImportError:  # pragma: no cover
        return None

    normalized_video_path = Path(normalized_video_path)
    output_path = Path(output_path)
    if not normalized_video_path.exists() or frame_idx < 0:
        return None

    cap = cv2.VideoCapture(str(normalized_video_path))
    if not cap.isOpened():
        return None
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            log.warning("keyframe_read_failed", extra={"frame_idx": frame_idx})
            return None

        if overlay_pose and pose_result is not None and 0 <= frame_idx < pose_result.num_frames:
            try:
                connections = _pose_connections()
                _draw_pose_on_frame(
                    frame,
                    pose_result.keypoints[frame_idx, :, :2],
                    pose_result.visibility[frame_idx],
                    connections,
                )
            except Exception as exc:  # 骨骼叠加失败不影响抽帧本身
                log.warning("keyframe_overlay_failed", extra={"error": str(exc)})

        output_path.parent.mkdir(parents=True, exist_ok=True)
        ok = cv2.imwrite(
            str(output_path),
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), _JPEG_QUALITY],
        )
        if not ok:
            log.warning("keyframe_imwrite_failed", extra={"output": str(output_path)})
            return None
        return output_path
    finally:
        cap.release()


def extract_issue_keyframes(
    normalized_video_path: Path | str,
    issues: list[DiagnosedIssue],
    pose_result: PoseResult,
    output_dir: Path | str,
) -> dict[str, Path]:
    """对每条 issue 按 `key_frame_timestamp` 抽帧。

    Args:
        normalized_video_path: 输入视频
        issues: T2 诊断结果
        pose_result: 用于叠加骨骼
        output_dir: 输出目录（每张 jpg 文件名为 `<issue_type>.jpg`）

    Returns:
        {issue_type: path}；抽帧失败的会缺席（不抛错）
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    fps = pose_result.fps if pose_result.fps > 0 else 30.0
    for issue in issues:
        if issue.key_frame_timestamp is None:
            continue
        frame_idx = int(round(issue.key_frame_timestamp * fps))
        # clip 到合法范围
        frame_idx = max(0, min(frame_idx, pose_result.num_frames - 1))
        out = output_dir / f"{issue.type}.jpg"
        result = extract_keyframe(
            normalized_video_path,
            frame_idx,
            out,
            pose_result=pose_result,
            overlay_pose=True,
        )
        if result is not None:
            paths[issue.type] = result
    return paths


# ============================================================
# 3. 骨骼时序 parquet
# ============================================================


def dump_pose_parquet(pose_result: PoseResult, output_path: Path | str) -> Path | None:
    """把姿态时序写成 parquet。

    Schema（行=帧）：
        frame_idx (int32)
        valid (bool)
        kp_x_0..kp_x_32  (float32)
        kp_y_0..kp_y_32  (float32)
        kp_z_0..kp_z_32  (float32)
        vis_0..vis_32   (float32)

    选 wide 表（132 列 × F 行）而非 long（F×33 行 × 5 列）：前端 mini-cdn
    拿 parquet 后按帧索引最快；wide 表的 schema 也方便 pandas + arrow 直接 zero-copy。
    """
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        log.warning("pyarrow_unavailable")
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    keypoints = pose_result.keypoints  # (F, 33, 3) float32
    visibility = pose_result.visibility  # (F, 33) float32
    valid = pose_result.valid_mask  # (F,) bool
    num_frames, num_lm, _ = keypoints.shape

    columns: dict[str, np.ndarray] = {
        "frame_idx": np.arange(num_frames, dtype=np.int32),
        "valid": valid.astype(np.bool_),
    }
    for axis_idx, axis_name in enumerate(("x", "y", "z")):
        for lm_idx in range(num_lm):
            columns[f"kp_{axis_name}_{lm_idx}"] = keypoints[:, lm_idx, axis_idx].astype(np.float32)
    for lm_idx in range(num_lm):
        columns[f"vis_{lm_idx}"] = visibility[:, lm_idx].astype(np.float32)

    try:
        table = pa.table(columns)
        pq.write_table(
            table,
            output_path,
            compression="zstd",  # zstd 比 snappy 小 30%，CPU 略高但单文件 < 200ms
            compression_level=3,
        )
    except Exception as exc:
        log.warning("parquet_write_failed", extra={"error": str(exc)})
        return None

    log.info(
        "pose_parquet_written",
        extra={
            "output": str(output_path),
            "frames": num_frames,
            "size_bytes": output_path.stat().st_size if output_path.exists() else 0,
        },
    )
    return output_path


# ============================================================
# 统一工具：临时目录上下文
# ============================================================


def make_artifacts_tmpdir(prefix: str = "ai_engine_t3_") -> Path:
    """造一个 tmp 目录用来放本轮分析的所有 derived assets，调用方自己清理。"""
    return Path(tempfile.mkdtemp(prefix=prefix))
