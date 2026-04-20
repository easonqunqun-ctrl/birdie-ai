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
