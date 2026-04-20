"""preprocess.py 单元测试。

分三层：
  1. 纯逻辑 / 数据结构（任何环境能跑）
  2. 合成视频质量门（需要 ffmpeg + opencv）
  3. 真实视频 happy path（需要 real/*.mp4）
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.errors import PoorQualityError, PreprocessError
from tests.conftest import needs_cv2, needs_ffmpeg

# ============================================================
# 第 1 层：纯 import / 常量（0 依赖）
# ============================================================


def test_module_importable() -> None:
    """保证 preprocess 模块即便没装 cv2/ffmpeg 也能 import；
    实际调用才会校验工具存在（_require_binary）。"""
    from app.pipeline import preprocess

    assert preprocess.TARGET_FPS == 30
    assert preprocess.TARGET_SHORT_SIDE == 720
    assert preprocess.MIN_DURATION_SEC < preprocess.MAX_DURATION_SEC


def test_preprocess_result_dataclass_shape() -> None:
    """PreprocessResult 的字段必须齐，T2 特征层会直接读这些字段。"""
    from app.pipeline.preprocess import PreprocessResult

    result = PreprocessResult(
        normalized_video_path=Path("/tmp/fake.mp4"),
        fps=30.0,
        num_frames=90,
        width=720,
        height=1280,
        duration_sec=3.0,
        clarity_score=150.0,
        stability_score=0.9,
        frame_loss_ratio=0.0,
        quality_score=0.85,
    )
    assert result.is_quality_ok is True

    poor = PreprocessResult(
        normalized_video_path=Path("/tmp/x.mp4"),
        fps=30.0,
        num_frames=0,
        width=720,
        height=1280,
        duration_sec=0.0,
        clarity_score=10.0,
        stability_score=0.1,
        frame_loss_ratio=0.5,
        quality_score=0.2,
    )
    assert poor.is_quality_ok is False


def test_preprocess_missing_file_raises() -> None:
    from app.pipeline.preprocess import preprocess_video

    with pytest.raises(PreprocessError):
        preprocess_video("/does/not/exist.mp4")


# ============================================================
# 第 2 层：合成视频质量门（需要 ffmpeg + opencv）
# ============================================================


@needs_ffmpeg
@needs_cv2
def test_too_short_video_raises(too_short_video: Path) -> None:
    """时长 < MIN_DURATION_SEC 的视频应该在 ffprobe 阶段就抛 PreprocessError。"""
    from app.pipeline.preprocess import preprocess_video

    with pytest.raises(PreprocessError) as exc_info:
        preprocess_video(str(too_short_video), min_duration=2.0)
    assert exc_info.value.code == 50101


@needs_ffmpeg
@needs_cv2
def test_blackscreen_triggers_poor_quality(blackscreen_video: Path) -> None:
    """纯黑视频应该被 clarity 门拦下（拉普拉斯方差接近 0）。"""
    from app.pipeline.preprocess import preprocess_video

    with pytest.raises(PoorQualityError) as exc_info:
        preprocess_video(str(blackscreen_video))
    assert exc_info.value.code == 50102


@needs_ffmpeg
@needs_cv2
def test_bouncing_box_passes_quality_gate(bouncing_box_video: Path, tmp_path: Path) -> None:
    """testsrc2 合成视频清晰度和稳定性都 OK，应通过质量门（但后续 pose 会检不到人）。

    这条用例验证：**画质好但无人物 ≠ 画质不足**，两个失败维度解耦。
    """
    from app.pipeline.preprocess import preprocess_video

    result = preprocess_video(str(bouncing_box_video), work_dir=tmp_path)
    assert result.num_frames > 60
    assert result.fps > 25  # 目标 30
    assert result.clarity_score >= 80  # 应远高于纯黑
    assert result.is_quality_ok


# ============================================================
# 第 3 层：真实视频 happy path（需要 real/*.mp4）
# ============================================================


@needs_ffmpeg
@needs_cv2
def test_real_video_normalizes_to_30fps_and_720p(real_video_path: Path, tmp_path: Path) -> None:
    """真实挥杆视频预处理后应该：
    - fps 归一化到 ~30
    - 短边不超过 720
    - 质量门通过
    """
    from app.pipeline.preprocess import preprocess_video

    result = preprocess_video(str(real_video_path), work_dir=tmp_path)

    # 帧率在 29-31 之间（ffmpeg `-r 30` 偶有浮点漂移）
    assert 29.0 <= result.fps <= 31.0

    # 短边 ≤ 720
    assert min(result.width, result.height) <= 720

    # 质量门：真实视频应该通过
    assert result.is_quality_ok
    assert result.num_frames >= 30  # 至少 1 秒 × 30fps
