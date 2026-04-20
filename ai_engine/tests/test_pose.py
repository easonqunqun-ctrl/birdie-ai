"""pose.py 单元测试。

分三层：
  1. 纯 import / 常量
  2. 合成视频失败分支（需要 mediapipe + cv2 + ffmpeg + synthetic videos）
  3. 真实视频 happy path（需要 real/*.mp4）
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.errors import NoPersonError, PoseModelError
from tests.conftest import needs_cv2, needs_ffmpeg, needs_mediapipe

# ============================================================
# 第 1 层：纯 import
# ============================================================


def test_module_importable() -> None:
    """即便没装 mediapipe/cv2，pose 模块本身（不调 estimate_poses）也能 import。"""
    from app.pipeline import pose

    assert pose.NUM_LANDMARKS == 33
    assert pose.LANDMARK_LEFT_WRIST == 15
    assert pose.LANDMARK_RIGHT_WRIST == 16
    assert pose.MIN_VALID_FRAME_RATIO == 0.7


def test_pose_result_dataclass() -> None:
    from app.pipeline.pose import PoseResult

    keypoints = np.zeros((10, 33, 3), dtype=np.float32)
    visibility = np.zeros((10, 33), dtype=np.float32)
    visibility[3:8] = 0.9  # 5 帧有效
    valid_mask = visibility.mean(axis=1) >= 0.5

    result = PoseResult(
        keypoints=keypoints,
        visibility=visibility,
        valid_mask=valid_mask,
        num_frames=10,
        fps=30.0,
    )
    assert result.num_frames == 10
    assert pytest.approx(result.valid_frame_ratio, abs=1e-6) == 0.5


def test_estimate_poses_missing_file() -> None:
    from app.pipeline.pose import estimate_poses

    with pytest.raises(PoseModelError):
        estimate_poses("/does/not/exist.mp4")


# ============================================================
# 第 2 层：合成视频失败分支
# ============================================================


@needs_mediapipe
@needs_cv2
@needs_ffmpeg
def test_no_person_video_raises(no_person_video: Path) -> None:
    """渐变色静态视频应该被 NoPersonError 拦下（MediaPipe 全帧无检测）。"""
    from app.pipeline.pose import estimate_poses

    with pytest.raises(NoPersonError) as exc_info:
        estimate_poses(no_person_video)
    assert exc_info.value.code == 50103


@needs_mediapipe
@needs_cv2
@needs_ffmpeg
def test_bouncing_box_raises_no_person(bouncing_box_video: Path) -> None:
    """testsrc2 合成视频有颜色有动但无人体，也应触发 NoPersonError。"""
    from app.pipeline.pose import estimate_poses

    with pytest.raises(NoPersonError):
        estimate_poses(bouncing_box_video)


# ============================================================
# 第 3 层：真实视频 happy path
# ============================================================


@needs_mediapipe
@needs_cv2
@needs_ffmpeg
def test_real_video_produces_valid_keypoints(real_video_path: Path, tmp_path: Path) -> None:
    """真实挥杆视频应该：
    - 关键点数组形状 (F, 33, 3)
    - 有效帧占比 ≥ 70%
    - 核心关键点（肩、腕）的平均可见度 ≥ 0.5
    """
    from app.pipeline.pose import (
        LANDMARK_LEFT_SHOULDER,
        LANDMARK_LEFT_WRIST,
        LANDMARK_RIGHT_SHOULDER,
        LANDMARK_RIGHT_WRIST,
        NUM_LANDMARKS,
        estimate_poses,
    )
    from app.pipeline.preprocess import preprocess_video

    # 先预处理到标准规格（否则 GolfDB 的 160×160 会对推理精度有影响）
    preproc = preprocess_video(str(real_video_path), work_dir=tmp_path)

    result = estimate_poses(preproc.normalized_video_path)

    assert result.keypoints.shape == (result.num_frames, NUM_LANDMARKS, 3)
    assert result.visibility.shape == (result.num_frames, NUM_LANDMARKS)
    assert result.valid_frame_ratio >= 0.7

    # 核心关键点的可见度
    core_landmarks = [
        LANDMARK_LEFT_SHOULDER,
        LANDMARK_RIGHT_SHOULDER,
        LANDMARK_LEFT_WRIST,
        LANDMARK_RIGHT_WRIST,
    ]
    core_vis = result.visibility[result.valid_mask][:, core_landmarks].mean()
    assert core_vis >= 0.5, f"核心关键点可见度过低：{core_vis:.3f}"


@needs_mediapipe
@needs_cv2
@needs_ffmpeg
def test_real_video_keypoints_in_normalized_range(real_video_path: Path, tmp_path: Path) -> None:
    """MediaPipe 输出的 x/y 是 [0, 1] 归一化坐标（y 向下），z 是相对深度。"""
    from app.pipeline.pose import estimate_poses
    from app.pipeline.preprocess import preprocess_video

    preproc = preprocess_video(str(real_video_path), work_dir=tmp_path)
    result = estimate_poses(preproc.normalized_video_path)

    valid_kp = result.keypoints[result.valid_mask]
    # x / y 在 [0, 1] 范围内（允许极少量越界，比如手伸出画面）
    in_range_x = ((valid_kp[..., 0] >= -0.1) & (valid_kp[..., 0] <= 1.1)).mean()
    in_range_y = ((valid_kp[..., 1] >= -0.1) & (valid_kp[..., 1] <= 1.1)).mean()
    assert in_range_x > 0.95
    assert in_range_y > 0.95
