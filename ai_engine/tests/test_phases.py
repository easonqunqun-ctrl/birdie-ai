"""W6-T2：阶段分割单测。"""

from __future__ import annotations

import pytest

from app.errors import NoSwingError
from app.pipeline.constants import PHASE_ORDER
from app.pipeline.phases import (
    MIN_SWING_FRAMES,
    PhaseSegmentResult,
    segment_phases,
)


def test_segment_phases_on_synthetic(synthetic_pose_result) -> None:
    """合成理想挥杆应该能分出六个阶段，各阶段的帧号符合预期顺序。"""
    result = segment_phases(synthetic_pose_result)

    assert isinstance(result, PhaseSegmentResult)
    assert set(result.phases.keys()) == set(PHASE_ORDER)

    # 四个关键帧定义在 f_setup=10, f_top=45, f_impact=65, f_finish=85
    # top_frame 应接近 45（y 最小点）
    assert abs(result.top_frame - 45) <= 3
    # impact_frame 在 top 之后、速度最大处；合成里 top→impact 线性过渡，
    # 速度恒定，argmax 可能回到 top+1。只要 > top 就行。
    assert result.impact_frame > result.top_frame

    # 阶段的单调性：setup.end < backswing.start ≤ backswing.end < top.start ≤ top.end
    #   < downswing.start ≤ downswing.end < impact.start ≤ impact.end < follow.start
    assert result.phases["setup"].end_frame <= result.phases["backswing"].start_frame
    assert result.phases["backswing"].end_frame < result.phases["top"].start_frame or \
        result.phases["backswing"].end_frame == result.phases["backswing"].start_frame
    assert result.phases["top"].end_frame <= result.phases["downswing"].start_frame
    assert result.phases["downswing"].end_frame <= result.phases["impact"].start_frame
    assert result.phases["impact"].end_frame < result.phases["follow_through"].start_frame

    # fps 透传
    assert result.fps == synthetic_pose_result.fps


def test_no_swing_for_static_video(synthetic_pose_result) -> None:
    """把整个合成序列固定在 setup 帧（无运动）应该抛 NoSwingError。"""
    static = synthetic_pose_result
    static.keypoints[:] = static.keypoints[10]  # 全部填 setup 帧
    with pytest.raises(NoSwingError):
        segment_phases(static)


def test_no_swing_for_too_short(synthetic_pose_result) -> None:
    """截短到低于 MIN_SWING_FRAMES 应该抛 NoSwingError。"""
    short = synthetic_pose_result
    short.keypoints = short.keypoints[: MIN_SWING_FRAMES - 2]
    short.visibility = short.visibility[: MIN_SWING_FRAMES - 2]
    short.valid_mask = short.valid_mask[: MIN_SWING_FRAMES - 2]
    short.num_frames = MIN_SWING_FRAMES - 2
    with pytest.raises(NoSwingError):
        segment_phases(short)


def test_handedness_right(synthetic_pose_result) -> None:
    """理想挥杆里左右手腕都在运动，主手选位移更大的那侧。
    合成中 left_wrist 明显挪得多（setup y=0.62 → top y=0.10 → impact y=0.63），
    所以 handedness 应该是 "right"（left wrist 更活跃 → lead = left 侧）。
    """
    result = segment_phases(synthetic_pose_result)
    assert result.handedness in {"right", "left"}
    # 合成的 left wrist 运动量 > right wrist，按我们的策略应选 right（lead=left）
    assert result.handedness == "right"
