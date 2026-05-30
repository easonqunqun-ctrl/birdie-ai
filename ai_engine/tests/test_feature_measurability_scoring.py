"""P2 机位可测性计分单测。"""

from __future__ import annotations

from app.pipeline.feature_measurability import (
    MIN_MEASURABILITY_TO_SCORE,
    sanitize_features,
)
from app.pipeline.scoring import score_all_phases, score_phase


def test_dtl_nelly_like_features_backswing_not_zero() -> None:
    """内莉·柯达 DTL 片：旋转读数失真时上杆不得 0 分。"""
    raw = {
        "shoulder_rotation_top": 11.837,
        "hip_rotation_top": 119.759,
        "x_factor": 0.0,
        "downswing_sequence": 2.0,
        "left_arm_straightness": 87.294,
        "top_wrist_position": 0.15,
        "spine_angle_setup": 47.074,
        "spine_angle_impact_delta": 16.988,
        "finish_height": 0.068,
        "finish_balance": 0.002,
        "tempo_ratio": 3.0,
    }
    features, _ = sanitize_features(raw, camera_angle="down_the_line")
    backswing = score_phase(
        features, "backswing", club_category="iron", camera_angle="down_the_line"
    )
    assert backswing >= 50
    assert backswing != 0

    scores = score_all_phases(
        features, club_category="iron", camera_angle="down_the_line"
    )
    assert scores["backswing"] >= 50
    assert scores["impact"] >= 80
    from app.pipeline.scoring import score_overall

    overall = score_overall(scores, club_category="iron", camera_angle="down_the_line", features=features)
    assert overall >= 85


def test_sanitize_strips_absurd_hip_rotation() -> None:
    raw = {"hip_rotation_top": 119.0, "x_factor": 5.0, "shoulder_rotation_top": 12.0}
    cleaned, warnings = sanitize_features(raw, camera_angle="down_the_line")
    assert "hip_rotation_top" not in cleaned
    assert "rotation_reading_unreliable" in warnings


def test_face_on_rotation_features_still_scored() -> None:
    """正面机位仍计旋转特征（measurability 高）。"""
    from app.pipeline.feature_measurability import measurability

    assert measurability("shoulder_rotation_top", "face_on") >= MIN_MEASURABILITY_TO_SCORE
    assert measurability("shoulder_rotation_top", "down_the_line") < MIN_MEASURABILITY_TO_SCORE
