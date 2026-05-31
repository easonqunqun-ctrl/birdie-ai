"""共享 pytest fixtures + 依赖/素材可用性探测。

关键约定
--------
- 如果 `mediapipe` 没装 → 需要它的测试自动 **skip**（不是 fail）
- 如果 `ffmpeg` 不在 PATH → 需要它的测试自动 **skip**
- 如果 `tests/fixtures/real/*.mp4` 没有 → 真实视频集成测试 **skip**
- 如果 `tests/fixtures/synthetic/*.mp4` 没有 → 合成视频测试 **skip**
  （用户需要先跑 `bash tests/fixtures/generate_synthetic.sh` 生成）

这样在三种环境下都能 `pytest` 不红：
  1. 开发机装了一切 + 有视频 → 全跑
  2. CI 只装了依赖但没视频 → 只跑"无视频"单测（import / 常量 / 数据结构）
  3. 评审机只想看类型 → `uv run pytest --co`（collect only）也不崩
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

# ============================================================
# 路径
# ============================================================

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REAL_DIR = FIXTURES_DIR / "real"
SYNTHETIC_DIR = FIXTURES_DIR / "synthetic"


# ============================================================
# 依赖探测
# ============================================================


def _has_module(name: str) -> bool:
    """不真正 import，只检查是否能找到。避免"没装 mediapipe 的机器"collect 就崩。"""
    import importlib.util

    return importlib.util.find_spec(name) is not None


HAS_MEDIAPIPE = _has_module("mediapipe")
HAS_CV2 = _has_module("cv2")
HAS_FFMPEG = shutil.which("ffmpeg") is not None
HAS_FFPROBE = shutil.which("ffprobe") is not None


# ============================================================
# skip 装饰器：测试文件里直接用
# ============================================================

needs_mediapipe = pytest.mark.skipif(
    not HAS_MEDIAPIPE,
    reason="mediapipe 未安装（在 ai_engine/ 下 `uv sync` 即可）",
)

needs_cv2 = pytest.mark.skipif(
    not HAS_CV2,
    reason="opencv-python-headless 未安装（在 ai_engine/ 下 `uv sync` 即可）",
)

needs_ffmpeg = pytest.mark.skipif(
    not (HAS_FFMPEG and HAS_FFPROBE),
    reason="ffmpeg/ffprobe 未安装（macOS: `brew install ffmpeg`，Linux: `apt install ffmpeg`）",
)


# ============================================================
# 视频素材探测
# ============================================================


def _first_video(directory: Path, patterns: tuple[str, ...] = ("*.mp4", "*.mov")) -> Path | None:
    if not directory.exists():
        return None
    for pattern in patterns:
        candidates = sorted(directory.glob(pattern))
        if candidates:
            return candidates[0]
    return None


@pytest.fixture(scope="session")
def real_video_path() -> Path:
    """第一段可用的真实挥杆视频。

    没有时 skip（而非 fail），方便 CI 无素材场景绕过。
    """
    video = _first_video(REAL_DIR)
    if video is None:
        pytest.skip(
            f"tests/fixtures/real/ 下无视频；请先 `bash {FIXTURES_DIR}/download_samples.sh` 或手动 drop",
        )
    return video


@pytest.fixture(scope="session")
def synthetic_videos() -> dict[str, Path]:
    """合成视频字典：键是 stem，值是路径。

    没有任何合成视频时 skip。
    """
    if not SYNTHETIC_DIR.exists() or not any(SYNTHETIC_DIR.glob("*.mp4")):
        pytest.skip(
            f"tests/fixtures/synthetic/ 下无视频；请先 `bash {FIXTURES_DIR}/generate_synthetic.sh` 生成",
        )
    return {p.stem: p for p in SYNTHETIC_DIR.glob("*.mp4")}


@pytest.fixture(scope="session")
def blackscreen_video(synthetic_videos: dict[str, Path]) -> Path:
    if "blackscreen" not in synthetic_videos:
        pytest.skip("blackscreen.mp4 缺失；跑 generate_synthetic.sh")
    return synthetic_videos["blackscreen"]


@pytest.fixture(scope="session")
def no_person_video(synthetic_videos: dict[str, Path]) -> Path:
    if "no_person" not in synthetic_videos:
        pytest.skip("no_person.mp4 缺失；跑 generate_synthetic.sh")
    return synthetic_videos["no_person"]


@pytest.fixture(scope="session")
def too_short_video(synthetic_videos: dict[str, Path]) -> Path:
    if "too_short" not in synthetic_videos:
        pytest.skip("too_short.mp4 缺失；跑 generate_synthetic.sh")
    return synthetic_videos["too_short"]


@pytest.fixture(scope="session")
def bouncing_box_video(synthetic_videos: dict[str, Path]) -> Path:
    if "bouncing_box" not in synthetic_videos:
        pytest.skip("bouncing_box.mp4 缺失；跑 generate_synthetic.sh")
    return synthetic_videos["bouncing_box"]


def resolve_manifest_fixture_video(
    case: dict,
    *,
    real_dir: Path = REAL_DIR,
) -> Path | None:
    """按 manifest case 的 ``fixture_file`` / ``alt_fixture_files`` 解析本地视频路径。"""
    candidates: list[str] = []
    primary = case.get("fixture_file")
    if primary:
        candidates.append(str(primary))
    candidates.extend(str(p) for p in case.get("alt_fixture_files") or [])
    for name in candidates:
        path = real_dir / name
        if path.is_file():
            return path
    return None


@pytest.fixture(scope="session")
def rotation_regression_manifest() -> dict:
    manifest_path = FIXTURES_DIR / "rotation_regression_manifest.json"
    if not manifest_path.is_file():
        pytest.skip("rotation_regression_manifest.json 缺失")
    import json

    return json.loads(manifest_path.read_text(encoding="utf-8"))


# ============================================================
# T2 合成关键点 fixture（不依赖真实视频，纯 numpy）
# ============================================================


@pytest.fixture(scope="function")
def synthetic_pose_result():
    """生成一个"理想挥杆"的合成 PoseResult。

    思路：
      - 90 帧 @ 30fps（3s 视频），关键点归一化坐标
      - 在 setup / top / impact / finish 四个关键帧人工摆位
      - 中间帧用线性插值过渡
      - 整套姿态设计成"分数应该较高、无明显 issue"的理想挥杆

    返回 PoseResult；测试可以直接往下游模块灌。
    """
    import numpy as np

    from app.pipeline.pose import (
        LANDMARK_LEFT_ANKLE,
        LANDMARK_LEFT_ELBOW,
        LANDMARK_LEFT_HIP,
        LANDMARK_LEFT_KNEE,
        LANDMARK_LEFT_SHOULDER,
        LANDMARK_LEFT_WRIST,
        LANDMARK_NOSE,
        LANDMARK_RIGHT_ANKLE,
        LANDMARK_RIGHT_ELBOW,
        LANDMARK_RIGHT_HIP,
        LANDMARK_RIGHT_KNEE,
        LANDMARK_RIGHT_SHOULDER,
        LANDMARK_RIGHT_WRIST,
        NUM_LANDMARKS,
        PoseResult,
    )

    num_frames = 90
    fps = 30.0
    keypoints = np.zeros((num_frames, NUM_LANDMARKS, 3), dtype=np.float32)
    visibility = np.ones((num_frames, NUM_LANDMARKS), dtype=np.float32) * 0.9

    # 关键帧索引
    f_setup = 10
    f_top = 45
    f_impact = 65
    f_finish = 85

    # 模板位置（x, y）：模拟"理想挥杆"，右撇子，正面视角（face-on）
    # y 越小越高；所有坐标归一化在 [0, 1]
    def setup_kp():
        kp = np.zeros((NUM_LANDMARKS, 3), dtype=np.float32)
        kp[LANDMARK_NOSE] = [0.50, 0.25, 0]
        kp[LANDMARK_LEFT_SHOULDER] = [0.45, 0.35, 0]
        kp[LANDMARK_RIGHT_SHOULDER] = [0.55, 0.35, 0]
        kp[LANDMARK_LEFT_ELBOW] = [0.42, 0.50, 0]
        kp[LANDMARK_RIGHT_ELBOW] = [0.58, 0.50, 0]
        kp[LANDMARK_LEFT_WRIST] = [0.46, 0.62, 0]
        kp[LANDMARK_RIGHT_WRIST] = [0.54, 0.62, 0]
        # 髋稍微前倾（比肩低一点，近似 30° 前倾）
        kp[LANDMARK_LEFT_HIP] = [0.47, 0.58, 0]
        kp[LANDMARK_RIGHT_HIP] = [0.53, 0.58, 0]
        kp[LANDMARK_LEFT_KNEE] = [0.47, 0.73, 0]
        kp[LANDMARK_RIGHT_KNEE] = [0.53, 0.73, 0]
        kp[LANDMARK_LEFT_ANKLE] = [0.47, 0.90, 0]
        kp[LANDMARK_RIGHT_ANKLE] = [0.53, 0.90, 0]
        return kp

    def top_kp():
        kp = setup_kp().copy()
        # 手腕升到头顶上方（y < nose.y）
        kp[LANDMARK_LEFT_WRIST] = [0.40, 0.10, 0]
        kp[LANDMARK_RIGHT_WRIST] = [0.42, 0.12, 0]
        kp[LANDMARK_LEFT_ELBOW] = [0.42, 0.25, 0]
        kp[LANDMARK_RIGHT_ELBOW] = [0.50, 0.28, 0]
        # 肩旋转 ~90°：右撇子，右肩向后（视角下远离镜头，y 略增），左肩向前（y 略减）
        # 用 2D 近似：左右肩线从 setup (L:0.45,0.35;R:0.55,0.35) → top (L:0.42,0.40;R:0.58,0.30)
        # 肩线角度 arctan2(0.30-0.40, 0.58-0.42) = arctan2(-0.10, 0.16) ≈ -32°；相对 setup 0° → 32° 偏离
        # 我们要 80°-100°，所以夹角更大些：
        kp[LANDMARK_LEFT_SHOULDER] = [0.48, 0.45, 0]
        kp[LANDMARK_RIGHT_SHOULDER] = [0.60, 0.25, 0]
        # 髋旋转较少
        kp[LANDMARK_LEFT_HIP] = [0.48, 0.60, 0]
        kp[LANDMARK_RIGHT_HIP] = [0.54, 0.56, 0]
        return kp

    def impact_kp():
        kp = setup_kp().copy()
        # 手腕回到 setup 附近位置、高速运动
        kp[LANDMARK_LEFT_WRIST] = [0.48, 0.63, 0]
        kp[LANDMARK_RIGHT_WRIST] = [0.52, 0.63, 0]
        # 髋打开（右侧往前）
        kp[LANDMARK_LEFT_HIP] = [0.45, 0.58, 0]
        kp[LANDMARK_RIGHT_HIP] = [0.56, 0.58, 0]
        kp[LANDMARK_LEFT_SHOULDER] = [0.46, 0.37, 0]
        kp[LANDMARK_RIGHT_SHOULDER] = [0.55, 0.36, 0]
        return kp

    def finish_kp():
        kp = impact_kp().copy()
        # 收杆手腕在肩上方
        kp[LANDMARK_LEFT_WRIST] = [0.45, 0.20, 0]
        kp[LANDMARK_RIGHT_WRIST] = [0.50, 0.22, 0]
        kp[LANDMARK_LEFT_ELBOW] = [0.45, 0.30, 0]
        kp[LANDMARK_RIGHT_ELBOW] = [0.52, 0.30, 0]
        return kp

    # 给四个关键帧填值
    keypoints[f_setup] = setup_kp()
    keypoints[f_top] = top_kp()
    keypoints[f_impact] = impact_kp()
    keypoints[f_finish] = finish_kp()

    # 线性插值填充
    def lerp(a, b, t):
        return a + (b - a) * t

    # [0, f_setup) → 复制 setup
    for f in range(0, f_setup):
        keypoints[f] = keypoints[f_setup]
    # [f_setup, f_top) 插值
    for f in range(f_setup + 1, f_top):
        t = (f - f_setup) / (f_top - f_setup)
        keypoints[f] = lerp(keypoints[f_setup], keypoints[f_top], t)
    # [f_top, f_impact) 插值
    for f in range(f_top + 1, f_impact):
        t = (f - f_top) / (f_impact - f_top)
        keypoints[f] = lerp(keypoints[f_top], keypoints[f_impact], t)
    # [f_impact, f_finish) 插值
    for f in range(f_impact + 1, f_finish):
        t = (f - f_impact) / (f_finish - f_impact)
        keypoints[f] = lerp(keypoints[f_impact], keypoints[f_finish], t)
    # [f_finish, num_frames) 保持收杆
    for f in range(f_finish + 1, num_frames):
        keypoints[f] = keypoints[f_finish]

    valid_mask = np.ones(num_frames, dtype=bool)
    return PoseResult(
        keypoints=keypoints,
        visibility=visibility,
        valid_mask=valid_mask,
        num_frames=num_frames,
        fps=fps,
    )
