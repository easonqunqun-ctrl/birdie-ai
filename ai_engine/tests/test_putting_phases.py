"""P2-M7-11 W23 · 推杆 4 阶段分割单测。

合成一段「回摆 → 顶点停顿 → 前推到球（速度峰）→ 收杆」的 lead 腕轨迹，
验证分割得到 setup < backstroke < impact < follow，且 impact 落在速度峰附近。
"""

from __future__ import annotations

import numpy as np
import pytest

from app.errors import NoSwingError
from app.pipeline.pose import (
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
    PoseResult,
)
from app.pipeline.putting.constants import PUTTING_PHASE_ORDER
from app.pipeline.putting.phases import (
    MIN_PUTTING_FRAMES,
    PuttingPhaseResult,
    segment_putting_phases,
)

_FPS = 30.0


def _putting_pose(n: int = 48) -> PoseResult:
    """lead=左腕沿 x：setup 静止 → 回摆后撤 → 顶点停顿 → 前推（impact 峰）→ 收杆减速。"""
    kp = np.zeros((n, 33, 3), dtype=np.float32)
    kp[:, :, 2] = 1.0
    # 肩/头保持稳定
    kp[:, LANDMARK_LEFT_SHOULDER, :2] = (0.45, 0.40)
    kp[:, LANDMARK_RIGHT_SHOULDER, :2] = (0.55, 0.40)
    # 右腕（trail）几乎不动，保证 lead=左腕
    kp[:, LANDMARK_RIGHT_WRIST, :2] = (0.52, 0.55)

    x = np.full(n, 0.50, dtype=np.float32)
    # setup: 0-7 静止 0.50
    # 回摆 8-20：0.50 → 0.42（缓慢后撤）
    x[8:21] = np.linspace(0.50, 0.42, 13)
    # 顶点停顿 21-24：~0.42
    x[21:25] = 0.42
    # 前推 25-34：0.42 → 0.62，越往后步长越大（impact 峰在末段）
    fwd = 0.42 + (np.linspace(0, 1, 10) ** 1.8) * (0.62 - 0.42)
    x[25:35] = fwd
    # 收杆 35-end：缓慢到 0.64
    x[35:] = np.linspace(0.62, 0.64, n - 35)
    kp[:, LANDMARK_LEFT_WRIST, 0] = x
    kp[:, LANDMARK_LEFT_WRIST, 1] = 0.55

    return PoseResult(
        keypoints=kp,
        visibility=np.ones((n, 33), dtype=np.float32),
        valid_mask=np.ones(n, dtype=bool),
        num_frames=n,
        fps=_FPS,
    )


def test_segment_returns_4_phases_in_order() -> None:
    res = segment_putting_phases(_putting_pose())
    assert isinstance(res, PuttingPhaseResult)
    assert set(res.phases) == set(PUTTING_PHASE_ORDER)
    s = res.phases["setup"]
    b = res.phases["backstroke"]
    i = res.phases["impact"]
    f = res.phases["follow"]
    # setup < backstroke < impact < follow（硬约束）
    assert s.end_frame < b.start_frame <= b.end_frame
    assert b.end_frame < i.start_frame == i.end_frame == res.impact_frame
    assert i.end_frame < f.start_frame <= f.end_frame


def test_impact_near_speed_peak() -> None:
    """impact 帧应落在前推末段（合成里速度峰在 ~33）。"""
    res = segment_putting_phases(_putting_pose())
    assert 28 <= res.impact_frame <= 35


def test_handedness_right_when_left_wrist_leads() -> None:
    res = segment_putting_phases(_putting_pose())
    assert res.handedness == "right"
    assert res.lead_wrist_idx == LANDMARK_LEFT_WRIST
    assert res.lead_shoulder_idx == LANDMARK_LEFT_SHOULDER


def test_too_short_video_raises() -> None:
    n = MIN_PUTTING_FRAMES - 1
    pose = PoseResult(
        keypoints=np.zeros((n, 33, 3), dtype=np.float32),
        visibility=np.ones((n, 33), dtype=np.float32),
        valid_mask=np.ones(n, dtype=bool),
        num_frames=n,
        fps=_FPS,
    )
    with pytest.raises(NoSwingError):
        segment_putting_phases(pose)


def test_no_motion_raises() -> None:
    n = 40
    pose = PoseResult(
        keypoints=np.zeros((n, 33, 3), dtype=np.float32),  # 全静止
        visibility=np.ones((n, 33), dtype=np.float32),
        valid_mask=np.ones(n, dtype=bool),
        num_frames=n,
        fps=_FPS,
    )
    with pytest.raises(NoSwingError):
        segment_putting_phases(pose)


def test_segment_feeds_features_end_to_end() -> None:
    """分割结果可直接喂 extract_putting_features，4 特征齐全且有限。"""
    import math

    from app.pipeline.putting.features import extract_putting_features

    pose = _putting_pose()
    res = segment_putting_phases(pose)
    feats = extract_putting_features(pose.keypoints, res)
    assert set(feats) == {"pendulum_stability", "head_stability", "face_alignment", "tempo_ratio"}
    for v in feats.values():
        assert math.isfinite(v)
