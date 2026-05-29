"""P2-M7-12 · 切杆特征 + 阶段 + 评分单测。"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.errors import NoSwingError
from app.pipeline.pose import (
    LANDMARK_LEFT_ANKLE,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_ANKLE,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
    PoseResult,
)
from app.pipeline.chipping.constants import CHIPPING_FEATURES, CHIPPING_PHASE_ORDER
from app.pipeline.chipping.features import extract_chipping_features
from app.pipeline.chipping.phases import segment_chipping_phases
from app.pipeline.chipping.scoring import score_chipping

_L_EAR = 7
_R_EAR = 8
_FPS = 30.0


def _chipping_pose(n: int = 50) -> PoseResult:
    kp = np.zeros((n, 33, 3), dtype=np.float32)
    kp[:, :, 2] = 1.0
    kp[:, LANDMARK_LEFT_SHOULDER, :2] = (0.45, 0.42)
    kp[:, LANDMARK_RIGHT_SHOULDER, :2] = (0.55, 0.42)
    kp[:, LANDMARK_LEFT_ANKLE, :2] = (0.44, 0.85)
    kp[:, LANDMARK_RIGHT_ANKLE, :2] = (0.56, 0.85)
    kp[:, _L_EAR, :2] = (0.44, 0.28)
    kp[:, _R_EAR, :2] = (0.56, 0.28)
    kp[:, LANDMARK_RIGHT_WRIST, :2] = (0.52, 0.55)

    x = np.full(n, 0.48, dtype=np.float32)
    y = np.full(n, 0.58, dtype=np.float32)
    # setup 静止
    # 上杆 8-22：腕升高（y 减小）到耳附近
    y[8:23] = np.linspace(0.58, 0.32, 15)
    x[8:23] = np.linspace(0.48, 0.46, 15)
    # 下杆到 impact 25-32
    y[23:33] = np.linspace(0.32, 0.56, 10)
    x[23:33] = np.linspace(0.46, 0.50, 10)
    y[33:] = 0.57
    kp[:, LANDMARK_LEFT_WRIST, 0] = x
    kp[:, LANDMARK_LEFT_WRIST, 1] = y

    return PoseResult(
        keypoints=kp,
        visibility=np.ones((n, 33), dtype=np.float32),
        valid_mask=np.ones(n, dtype=bool),
        num_frames=n,
        fps=_FPS,
    )


def test_segment_returns_4_phases() -> None:
    res = segment_chipping_phases(_chipping_pose())
    assert set(res.phases) == set(CHIPPING_PHASE_ORDER)
    assert res.phases["setup"].end_frame < res.phases["backswing"].start_frame
    assert res.phases["backswing"].end_frame < res.phases["impact"].start_frame
    assert res.phases["impact"].end_frame < res.phases["follow"].start_frame


def test_extract_3_finite_features() -> None:
    pose = _chipping_pose()
    phases = segment_chipping_phases(pose)
    feats = extract_chipping_features(pose.keypoints, phases)
    assert set(feats) == {f["name"] for f in CHIPPING_FEATURES}
    for v in feats.values():
        assert math.isfinite(v)


def test_score_chipping_ideal_band() -> None:
    feats = {
        "half_swing_amplitude": 0.45,
        "face_open_angle": 10.0,
        "contact_point_quality": 90.0,
    }
    out = score_chipping(feats)
    assert out["overall"] >= 85
    assert set(out["phases"]) == set(CHIPPING_PHASE_ORDER)


def test_no_motion_raises() -> None:
    n = 40
    pose = PoseResult(
        keypoints=np.zeros((n, 33, 3), dtype=np.float32),
        visibility=np.ones((n, 33), dtype=np.float32),
        valid_mask=np.ones(n, dtype=bool),
        num_frames=n,
        fps=_FPS,
    )
    with pytest.raises(NoSwingError):
        segment_chipping_phases(pose)
