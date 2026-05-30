"""可信度量与 overall 校准单测。"""

from __future__ import annotations

from app.pipeline.constants import FEATURES
from app.pipeline.score_trust import (
    WARN_SCORE_LOW_TRUST,
    calibrate_trusted_overall,
)

_ALL_FEATURE_NAMES = [f["name"] for f in FEATURES]


def test_broom_like_low_trust_capped_below_pro() -> None:
    """低可信 / 可测维度少 → 总分保守，与职业片拉开差距。"""
    broom_phase = {
        "setup": 55,
        "backswing": 50,
        "top": 50,
        "downswing": 58,
        "impact": 60,
        "follow_through": 52,
    }
    low_conf = {n: 0.35 for n in _ALL_FEATURE_NAMES}
    broom_score, warns = calibrate_trusted_overall(
        54,
        broom_phase,
        feature_confidences=low_conf,
        analysis_confidence=0.45,
        quality_warnings=[],
        camera_angle="face_on",
    )
    assert broom_score <= 48
    assert WARN_SCORE_LOW_TRUST in warns

    pro_phase = {
        "setup": 82,
        "backswing": 50,
        "top": 72,
        "downswing": 88,
        "impact": 90,
        "follow_through": 85,
    }
    high_conf = {n: 0.82 for n in _ALL_FEATURE_NAMES}
    pro_score, pro_warns = calibrate_trusted_overall(
        65,
        pro_phase,
        feature_confidences=high_conf,
        analysis_confidence=0.72,
        quality_warnings=[],
        camera_angle="down_the_line",
    )
    assert pro_score >= 68
    assert WARN_SCORE_LOW_TRUST not in pro_warns
    assert pro_score - broom_score >= 20


def test_moderate_trust_pulls_toward_neutral() -> None:
    phase = {p: 62 for p in (
        "setup", "backswing", "top", "downswing", "impact", "follow_through"
    )}
    conf = {n: 0.52 for n in (
        "downswing_sequence",
        "wrist_release_timing",
        "wrist_release_angle",
        "spine_angle_impact_delta",
        "tempo_ratio",
    )}
    adjusted, _ = calibrate_trusted_overall(
        62,
        phase,
        feature_confidences=conf,
        analysis_confidence=0.58,
        quality_warnings=[],
        camera_angle="face_on",
    )
    assert 55 <= adjusted <= 62
