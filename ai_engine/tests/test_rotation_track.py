"""P2-M7-R1 · 多帧旋转轨迹 + B2 三估计器单测."""

from __future__ import annotations

import numpy as np

from app.pipeline.phases import PhaseInfo, PhaseSegmentResult
from app.pipeline.pose import (
    LANDMARK_LEFT_HIP,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_HIP,
    LANDMARK_RIGHT_SHOULDER,
)
from app.pipeline.rotation_track import (
    ESTIMATOR_DISAGREEMENT_DEG,
    WARN_ESTIMATOR_DISAGREEMENT,
    apply_rotation_track,
    compute_rotation_features,
    compute_rotation_track,
    fuse_rotation_estimators,
)


def _fake_phases(*, top_frame: int = 15) -> PhaseSegmentResult:
    return PhaseSegmentResult(
        phases={
            "setup": PhaseInfo(0, 5, 2),
            "backswing": PhaseInfo(5, 14, 10),
            "top": PhaseInfo(top_frame, top_frame, top_frame),
            "downswing": PhaseInfo(16, 20, 18),
            "impact": PhaseInfo(21, 21, 21),
            "follow_through": PhaseInfo(22, 29, 25),
        },
        swing_start=5,
        swing_end=25,
        top_frame=top_frame,
        impact_frame=21,
        handedness="right",
        lead_wrist_idx=LANDMARK_LEFT_WRIST,
        lead_shoulder_idx=LANDMARK_LEFT_SHOULDER,
        fps=30.0,
    )


def _frame_with_shoulder_angle(angle_deg: float, *, torso_shift: float = 0.0) -> np.ndarray:
    """构造单帧 33 点；肩线角 + 可选胸廓 shift（估计器 B）。"""
    kp = np.zeros((33, 3), dtype=np.float32)
    rad = np.deg2rad(angle_deg)
    half = 0.12
    kp[LANDMARK_LEFT_SHOULDER, 0] = 0.5 - half * np.cos(rad) - torso_shift
    kp[LANDMARK_LEFT_SHOULDER, 1] = 0.5 - half * np.sin(rad)
    kp[LANDMARK_RIGHT_SHOULDER, 0] = 0.5 + half * np.cos(rad) - torso_shift
    kp[LANDMARK_RIGHT_SHOULDER, 1] = 0.5 + half * np.sin(rad)
    kp[LANDMARK_LEFT_HIP, 0] = 0.45 - torso_shift * 0.5
    kp[LANDMARK_LEFT_HIP, 1] = 0.65
    kp[LANDMARK_RIGHT_HIP, 0] = 0.55 - torso_shift * 0.5
    kp[LANDMARK_RIGHT_HIP, 1] = 0.65
    return kp


def test_rotation_track_uses_backswing_max_not_setup_only() -> None:
    phases = _fake_phases(top_frame=12)
    num_frames = 20
    keypoints = np.stack(
        [_frame_with_shoulder_angle(0.0 if f <= 5 else 45.0) for f in range(num_frames)]
    )
    rot = compute_rotation_features(
        keypoints, phases, camera_angle="face_on", existing_features={"top_wrist_position": 0.2}
    )
    assert rot["shoulder_rotation_top"] is not None
    assert rot["shoulder_rotation_top"] >= 40.0


def test_rotation_track_top_window_median_beats_misplaced_top() -> None:
    phases = _fake_phases(top_frame=10)
    angles = [0.0] * 6 + [10.0, 25.0, 40.0, 48.0, 5.0, 46.0, 50.0, 48.0] + [45.0] * 6
    keypoints = np.stack([_frame_with_shoulder_angle(a) for a in angles[:20]])
    rot = compute_rotation_features(keypoints, phases, camera_angle="face_on")
    assert rot["shoulder_rotation_top"] is not None
    assert rot["shoulder_rotation_top"] >= 45.0


def test_rotation_track_rejects_low_shoulder_with_high_wrist() -> None:
    phases = _fake_phases()
    keypoints = np.stack([_frame_with_shoulder_angle(0.0) for _ in range(20)])
    features = {"top_wrist_position": 0.2, "left_arm_straightness": 165.0}
    rot = compute_rotation_features(
        keypoints, phases, existing_features=features, camera_angle="face_on"
    )
    assert rot["shoulder_rotation_top"] is None


def test_apply_rotation_track_strips_unreliable_keys() -> None:
    phases = _fake_phases()
    keypoints = np.stack([_frame_with_shoulder_angle(0.0) for _ in range(20)])
    out = apply_rotation_track(
        {"shoulder_rotation_top": 3.0, "top_wrist_position": 0.2, "left_arm_straightness": 170.0},
        keypoints,
        phases,
        camera_angle="face_on",
    )
    assert "shoulder_rotation_top" not in out
    assert out["top_wrist_position"] == 0.2


def test_estimator_b_torso_detects_rotation() -> None:
    phases = _fake_phases(top_frame=12)
    keypoints = np.stack(
        [
            _frame_with_shoulder_angle(0.0, torso_shift=0.0 if f <= 5 else 0.08)
            for f in range(20)
        ]
    )
    result = compute_rotation_track(keypoints, phases, camera_angle="face_on")
    assert result.estimator_b is not None
    assert result.estimator_b > 5.0


def test_estimator_c_min_from_high_wrist() -> None:
    phases = _fake_phases()
    keypoints = np.stack([_frame_with_shoulder_angle(0.0) for _ in range(20)])
    result = compute_rotation_track(
        keypoints,
        phases,
        camera_angle="face_on",
        existing_features={"top_wrist_position": 0.18, "left_arm_straightness": 168.0},
    )
    assert result.estimator_c_min == 35.0


def test_fuse_dtl_skips_rotation_dimensions() -> None:
    result = fuse_rotation_estimators(
        estimator_a=80.0,
        estimator_b=70.0,
        estimator_c_min=None,
        hip_rotation=40.0,
        camera_angle="down_the_line",
        visibility_mean=0.9,
    )
    assert result.shoulder_rotation_top is None
    assert result.hip_rotation_top is None
    assert result.rotation_confidence == 0.0


def test_fuse_vetoes_low_a_when_c_min_higher() -> None:
    result = fuse_rotation_estimators(
        estimator_a=10.0,
        estimator_b=55.0,
        estimator_c_min=35.0,
        hip_rotation=30.0,
        camera_angle="face_on",
        visibility_mean=0.9,
    )
    assert result.estimator_a == 10.0
    assert result.shoulder_rotation_top is not None
    assert result.shoulder_rotation_top >= 45.0


def test_rotation_confidence_drops_on_estimator_disagreement() -> None:
    """AC-B3 · |A−B|>25° → confidence 下降 + estimator_disagreement warning."""
    agree = fuse_rotation_estimators(
        estimator_a=60.0,
        estimator_b=62.0,
        estimator_c_min=None,
        hip_rotation=35.0,
        camera_angle="face_on",
        visibility_mean=0.9,
    )
    disagree = fuse_rotation_estimators(
        estimator_a=60.0,
        estimator_b=60.0 + ESTIMATOR_DISAGREEMENT_DEG + 5.0,
        estimator_c_min=None,
        hip_rotation=35.0,
        camera_angle="face_on",
        visibility_mean=0.9,
    )
    assert disagree.rotation_confidence < agree.rotation_confidence
    assert WARN_ESTIMATOR_DISAGREEMENT in disagree.quality_warnings


def test_track_result_out_populated() -> None:
    phases = _fake_phases(top_frame=12)
    keypoints = np.stack(
        [_frame_with_shoulder_angle(0.0 if f <= 5 else 52.0) for f in range(20)]
    )
    meta: list = []
    apply_rotation_track(
        {"top_wrist_position": 0.15},
        keypoints,
        phases,
        camera_angle="face_on",
        track_result_out=meta,
    )
    assert len(meta) == 1
    assert meta[0].rotation_confidence > 0.0
    assert meta[0].estimator_a is not None
    assert meta[0].estimator_a >= 45.0
