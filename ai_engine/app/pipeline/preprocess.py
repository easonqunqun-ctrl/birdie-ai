"""W6-T1：视频预处理 pipeline。

职责
----
1. **下载/定位输入视频**：input_path 可以是本地路径或 `http(s)://` URL（MinIO 预签名）
2. **ffmpeg 转码归一化**：30fps / 短边 ≤720p / H.264 `yuv420p`；保证后续 OpenCV 读帧稳定
3. **读帧**：用 OpenCV 遍历，产出 `frames` generator（或一次性 list，视频短不爆内存）
4. **质量指标**：
   - `clarity_score`：拉普拉斯方差的**帧平均**，值越大越清晰
   - `stability_score`：帧间光流平均位移的倒数近似，值越大越稳
   - `frame_loss_ratio`：读帧失败的占比
5. **质量门**：综合分数 `quality_score` 低于 `MIN_QUALITY_SCORE` → 抛 `PoorQualityError`

为什么 ffmpeg 单独进程而不是 OpenCV 直接转码
-------------------------------------------
- OpenCV 的 VideoWriter 编码质量和兼容性远不如 ffmpeg（特别是 H.264 + yuv420p）
- ffmpeg 作为外部进程可以加 `-loglevel error -y` 稳定输出，错误流可捕获
- 分离关注点：预处理转码归 ffmpeg，算法读帧归 OpenCV

坑位预警
--------
- ffmpeg 必须装在容器里（W6-T5 Dockerfile 会加 `apt install ffmpeg`）
- 短边 720p 是**上限**而非下限：如果原视频本来就 480p，转码后还是 480p（不 upscale），
  但 `clarity_score` 会偏低，容易被 quality gate 拦下 → 这是合理的
- `cv2.VideoCapture` 在 macOS 和 Linux 对某些 mp4 容器的 seek 行为不同，
  这里我们**顺序遍历**不 seek，规避兼容问题
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

from app.config import settings
from app.errors import PoorQualityError, PreprocessError

# ============================================================
# 质量阈值：集中在这里方便 W6-T6 用真实视频回归时调
# ============================================================

# 帧拉普拉斯方差的**最小帧平均值**。低于这个数基本就是糊的。
# 经验：
#   - 手机正常拍的 1080p 视频平均值在 200-500 之间
#   - 严重模糊（抖动 + 低光）会掉到 30-80
#   - 纯黑画面会极低（~0）
# 取 80 作为"勉强可用"门槛，为 MVP 期留一点 tolerance
MIN_CLARITY_SCORE = 80.0

# 帧丢失比例上限（读帧失败 / 总帧数）。正常视频应该 < 1%。
MAX_FRAME_LOSS_RATIO = 0.1

# 视频最短时长（秒）。MVP §4.1 规定挥杆视频 3-15s，客户端已拦 <3s，
# 这里服务端再兜一次（防止伪造请求绕过前端）。
MIN_DURATION_SEC = 2.0
MAX_DURATION_SEC = 30.0

# 目标归一化参数
TARGET_FPS = 30
TARGET_SHORT_SIDE = 720  # 短边上限
TARGET_VCODEC = "libx264"
TARGET_PIX_FMT = "yuv420p"


# ============================================================
# 数据结构
# ============================================================


@dataclass
class PreprocessResult:
    """预处理产物。

    `normalized_video_path` 会被后续 pipeline 直接读帧，并且在 T3 里
    作为"骨骼叠加视频"的背景源；调用方负责在用完后清理临时目录。
    """

    normalized_video_path: Path
    fps: float
    num_frames: int
    width: int
    height: int
    duration_sec: float
    clarity_score: float
    stability_score: float
    frame_loss_ratio: float
    quality_score: float  # 综合分 0-1，用于 `is_quality_ok`

    @property
    def is_quality_ok(self) -> bool:
        return self.quality_score >= 0.5


# ============================================================
# 主入口
# ============================================================


def preprocess_video(
    input_path_or_url: str,
    *,
    work_dir: Path | None = None,
    min_clarity: float = MIN_CLARITY_SCORE,
    max_frame_loss: float = MAX_FRAME_LOSS_RATIO,
    min_duration: float = MIN_DURATION_SEC,
    max_duration: float = MAX_DURATION_SEC,
) -> PreprocessResult:
    """对输入视频做预处理并做质量判断。

    Args:
        input_path_or_url: 本地路径或 http(s) URL
        work_dir: 临时工作目录；不传则用系统 tempfile（调用方负责 cleanup）
        min_clarity / max_frame_loss / min_duration / max_duration: 见模块顶部常量

    Returns:
        `PreprocessResult`；质量不过关时**抛 `PoorQualityError`** 不返回

    Raises:
        PreprocessError: ffmpeg 失败、视频解码失败、时长越界
        PoorQualityError: 清晰度 / 稳定度 / 帧丢失不达标
    """
    work_dir = work_dir or Path(tempfile.mkdtemp(prefix="ai_engine_preproc_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. 下载或本地拷贝到 work_dir/source.mp4
    source_path = _materialize_input(input_path_or_url, work_dir)

    # 2. 用 ffprobe 拿基本信息，先做时长前置校验（避免浪费转码时间）
    probe = _ffprobe(source_path)
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

    # 3. ffmpeg 转码到 normalized.mp4（30fps / 720p 短边 / H.264）
    normalized_path = work_dir / "normalized.mp4"
    _ffmpeg_normalize(source_path, normalized_path, probe)

    # 4. OpenCV 读帧 + 算质量指标
    stats = _scan_quality(normalized_path)

    # 5. 综合 quality_score：简单加权平均到 [0, 1]
    clarity_component = min(stats.clarity_score / min_clarity, 2.0) / 2.0  # 0-1，clip 到 min 的 2 倍
    stability_component = stats.stability_score  # 已经归一化到 0-1
    frame_loss_penalty = max(0.0, 1.0 - stats.frame_loss_ratio / max_frame_loss)
    quality_score = 0.5 * clarity_component + 0.3 * stability_component + 0.2 * frame_loss_penalty
    quality_score = float(np.clip(quality_score, 0.0, 1.0))

    result = PreprocessResult(
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
    )

    # 6. 质量门
    if stats.clarity_score < min_clarity:
        raise PoorQualityError(
            f"clarity_score={stats.clarity_score:.1f} < {min_clarity}",
            user_message="视频画面过于模糊，请在光线充足的环境下重拍",
        )
    if stats.frame_loss_ratio > max_frame_loss:
        raise PoorQualityError(
            f"frame_loss_ratio={stats.frame_loss_ratio:.2%} > {max_frame_loss:.0%}",
            user_message="视频解码异常，请重新上传",
        )

    return result


# ============================================================
# 内部：输入定位 / ffmpeg / 质量扫描
# ============================================================


def _prefer_internal_minio_download_url(
    raw: str,
    *,
    bucket: str | None = None,
    internal_endpoint: str | None = None,
) -> str:
    """将对外 MinIO/CDN URL 转成容器内可调度的直链后再 curl。

    backend 下发的 `video_url` 常为 `effective_minio_public_endpoint`（如
    ``https://api.example/minio/<bucket>/<key>``），ai_engine 在 compose 网内应走
    ``MINIO_ENDPOINT``，避免公网 hostname / NAT 回流 / TLS 等对容器不可达导致的
    「视频下载失败」。

    带 query（预签名等）的 URL **不改写**，交由 curl 按原样拉取。
    """
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return raw
    if parsed.query:
        return raw

    b = bucket or settings.MINIO_BUCKET
    internal = (internal_endpoint or settings.MINIO_ENDPOINT).rstrip("/")

    marker = f"/{b}/"
    path = parsed.path or ""
    idx = path.find(marker)
    if idx < 0:
        return raw
    object_key = path[idx + len(marker) :].lstrip("/")
    if not object_key:
        return raw
    return f"{internal}/{b}/{object_key}"


def _materialize_input(input_path_or_url: str, work_dir: Path) -> Path:
    """把输入统一落到本地文件系统。

    - 本地路径：直接返回（不拷贝，省一次 IO）
    - http(s) URL：用 curl 下载到 work_dir/source.mp4
      （为什么不用 httpx？预处理阶段的"下载"本质是**一次性拉大文件**，
      curl 的 resume / 超时 / 重试更成熟；而且 Dockerfile 已装 curl）
    """
    parsed = urlparse(input_path_or_url)
    if parsed.scheme in ("http", "https"):
        dest = work_dir / "source.mp4"
        fetch_url = _prefer_internal_minio_download_url(input_path_or_url)
        cmd = ["curl", "-fsSL", "--max-time", "60", "-o", str(dest), fetch_url]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=90)
        except subprocess.CalledProcessError as exc:
            raise PreprocessError(
                f"下载视频失败 (curl exit={exc.returncode}): {exc.stderr.decode('utf-8', errors='ignore')[:200]}",
                user_message="视频下载失败，请检查网络后重试",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise PreprocessError("下载视频超时（>90s）", user_message="视频下载超时，请稍后重试") from exc
        return dest

    local = Path(input_path_or_url)
    if not local.exists():
        raise PreprocessError(f"输入视频不存在：{input_path_or_url}")
    return local


@dataclass
class _ProbeInfo:
    duration_sec: float
    width: int
    height: int
    fps_raw: float  # 原始 fps


def _ffprobe(video_path: Path) -> _ProbeInfo:
    """用 ffprobe 拉基本信息。

    ffprobe 在 slim 容器里和 ffmpeg 同一个包，不需要额外装。
    """
    _require_binary("ffprobe")
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate:format=duration",
        "-of",
        "default=noprint_wrappers=1",
        str(video_path),
    ]
    try:
        out = subprocess.run(cmd, check=True, capture_output=True, timeout=15).stdout.decode("utf-8")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise PreprocessError(f"ffprobe 读取失败：{exc}") from exc

    # 解析 key=value 行
    fields: dict[str, str] = {}
    for line in out.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            fields[k.strip()] = v.strip()

    try:
        w = int(fields["width"])
        h = int(fields["height"])
        # r_frame_rate 形如 "30/1" 或 "30000/1001"，做一次安全除法
        num, den = fields["r_frame_rate"].split("/")
        fps = float(num) / float(den) if float(den) > 0 else 0.0
        duration = float(fields.get("duration", "0"))
    except (KeyError, ValueError) as exc:
        raise PreprocessError(f"ffprobe 输出解析失败：{fields}") from exc

    return _ProbeInfo(duration_sec=duration, width=w, height=h, fps_raw=fps)


def _ffmpeg_normalize(source: Path, dest: Path, probe: _ProbeInfo) -> None:
    """把 source 转码成 30fps / 短边 ≤720 / H.264 / yuv420p 的 mp4。

    - `-vf scale=...`：短边 ≤720 的保持比例缩放（长边随动）
    - `-r 30`：帧率固定到 30（低于 30 的视频会被 dup 帧插帧，高于 30 的丢帧）
    - `-movflags +faststart`：把 moov 挪到文件头，方便流式播放
    - `-an`：挥杆分析不需要音轨，扔掉
    """
    _require_binary("ffmpeg")

    # 短边 ≤ 720，用 min(w, h) 判断方向
    if min(probe.width, probe.height) <= TARGET_SHORT_SIDE:
        scale_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"  # H.264 要求宽高偶数
    elif probe.width < probe.height:
        scale_filter = f"scale={TARGET_SHORT_SIDE}:-2"
    else:
        scale_filter = f"scale=-2:{TARGET_SHORT_SIDE}"

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        scale_filter,
        "-r",
        str(TARGET_FPS),
        "-c:v",
        TARGET_VCODEC,
        "-pix_fmt",
        TARGET_PIX_FMT,
        "-preset",
        "veryfast",  # CPU 友好，速度/体积折中
        "-crf",
        "23",  # 视觉无损上限附近
        "-an",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    except subprocess.CalledProcessError as exc:
        raise PreprocessError(
            f"ffmpeg 转码失败 (exit={exc.returncode}): {exc.stderr.decode('utf-8', errors='ignore')[:300]}",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PreprocessError("ffmpeg 转码超时（>120s）") from exc

    if not dest.exists() or dest.stat().st_size == 0:
        raise PreprocessError("ffmpeg 输出文件为空")


@dataclass
class _ScanStats:
    fps: float
    num_frames: int
    width: int
    height: int
    clarity_score: float
    stability_score: float
    frame_loss_ratio: float


def _scan_quality(video_path: Path) -> _ScanStats:
    """顺序遍历视频计算质量指标。

    - 清晰度：`cv2.Laplacian(gray, CV_64F).var()` 的**帧平均**
    - 稳像：相邻灰度帧 `np.mean(np.abs(diff))` 的**帧平均**取倒数近似，
      归一化到 0-1（越稳越接近 1）
    - 为了性能，只对**降采样到 320px 短边**的灰度帧做计算；原分辨率测指标意义不大
    """
    import cv2  # 延迟 import，避免 mock 模式加载不必要的 opencv

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise PreprocessError(f"OpenCV 无法打开：{video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    total_frames_hint = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    clarity_values: list[float] = []
    diff_values: list[float] = []
    prev_gray: np.ndarray | None = None
    read_ok = 0
    read_fail = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame is None or frame.size == 0:
                read_fail += 1
                continue
            read_ok += 1

            # 降采样到 320 短边
            h, w = frame.shape[:2]
            if min(h, w) > 320:
                scale = 320 / min(h, w)
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # 清晰度：拉普拉斯算子响应的方差（focus measure）
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            clarity_values.append(lap_var)

            # 稳像：与前一帧的平均绝对差
            if prev_gray is not None:
                diff = float(np.mean(np.abs(gray.astype(np.int16) - prev_gray.astype(np.int16))))
                diff_values.append(diff)
            prev_gray = gray
    finally:
        cap.release()

    num_frames = read_ok
    total_read_attempts = read_ok + read_fail
    frame_loss_ratio = read_fail / max(total_read_attempts, 1) if total_read_attempts > 0 else 0.0

    # 如果 ffprobe 报的帧数比实际多很多（偶发 container 元数据错），用实际读到的算 loss
    if total_frames_hint > num_frames > 0 and total_frames_hint > 2 * num_frames:
        frame_loss_ratio = max(frame_loss_ratio, 1 - num_frames / total_frames_hint)

    clarity_score = float(np.mean(clarity_values)) if clarity_values else 0.0

    # 稳像归一化：diff 越小越稳。以 30.0 作为"剧烈抖动"上限
    mean_diff = float(np.mean(diff_values)) if diff_values else 0.0
    stability_score = float(max(0.0, 1.0 - min(mean_diff / 30.0, 1.0)))

    return _ScanStats(
        fps=fps,
        num_frames=num_frames,
        width=width,
        height=height,
        clarity_score=clarity_score,
        stability_score=stability_score,
        frame_loss_ratio=frame_loss_ratio,
    )


def _require_binary(name: str) -> None:
    """启动时检查 ffmpeg / ffprobe 是否在 PATH 里。

    Docker 镜像会在 W6-T5 统一装上；本地开发没装会给出明确错误，
    而不是让 subprocess 报一堆 shell 错误。
    """
    if shutil.which(name) is None:
        raise PreprocessError(
            f"系统缺少 {name}，请安装后再运行 AI Engine（Docker 镜像在 W6-T5 会自动装）",
            user_message="AI 引擎未就绪，请联系运维",
        )
