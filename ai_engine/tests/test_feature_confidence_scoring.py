"""计分前 feature confidence 过滤单测。"""

from __future__ import annotations

from app.pipeline.scoring import score_phase
from app.pipeline.score_trust import MIN_FEATURE_CONFIDENCE_TO_SCORE


def test_low_confidence_feature_excluded_from_phase_score() -> None:
    features = {
        "spine_angle_setup": 30.0,
        "knee_flexion_setup": 25.0,
    }
    high = score_phase(
        features,
        "setup",
        club_category="iron",
        camera_angle="face_on",
        feature_confidences={
            "spine_angle_setup": 0.85,
            "knee_flexion_setup": 0.80,
        },
    )
    low = score_phase(
        features,
        "setup",
        club_category="iron",
        camera_angle="face_on",
        feature_confidences={
            "spine_angle_setup": MIN_FEATURE_CONFIDENCE_TO_SCORE - 0.1,
            "knee_flexion_setup": 0.80,
        },
    )
    assert high > low
    assert low >= 50  # 单特征仍参与，不应崩
