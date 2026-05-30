"""内莉·柯达 DTL 转播片：计分 / 诊断回归（P2 v0.3）。"""

from __future__ import annotations

from app.pipeline.feature_measurability import sanitize_features
from app.pipeline.real_pipeline_v2 import diagnose_v2
from app.pipeline.scoring import score_all_phases, score_overall, score_phase
from app.pipeline.score_trust import calibrate_trusted_overall

# CVM live 重跑抽到的真实读数（2026-05-30）
NELLY_LIVE = {
    "downswing_sequence": 3.0,
    "finish_balance": 0.005,
    "finish_height": -0.086,
    "head_lateral_shift": 0.041,
    "hip_rotation_top": 164.724,
    "knee_flexion_setup": 149.706,
    "left_arm_straightness": 92.847,
    "shoulder_rotation_top": 176.106,
    "spine_angle_impact_delta": 1.599,
    "spine_angle_setup": 45.356,
    "tempo_ratio": 13.5,
    "top_wrist_position": -0.076,
    "wrist_release_angle": 114.95,
    "wrist_release_timing": 0.5,
    "x_factor": 11.382,
}

# 历史快照（回归：旧 fixture 仍应 ≥85）
NELLY_SNAPSHOT = {
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


def _score_nelly(raw: dict[str, float], *, analysis_confidence: float = 0.53) -> tuple[int, dict[str, int]]:
    from app.pipeline.feature_measurability import WARN_ANGLE_LIMITED_SCORING

    features, warns = sanitize_features(raw, camera_angle="down_the_line")
    if WARN_ANGLE_LIMITED_SCORING not in warns:
        warns = [*warns, WARN_ANGLE_LIMITED_SCORING]
    scores = score_all_phases(
        features, club_category="iron", camera_angle="down_the_line"
    )
    overall = score_overall(
        scores,
        club_category="iron",
        camera_angle="down_the_line",
        features=features,
    )
    high_conf = {n: 0.72 for n in features}
    calibrated, _ = calibrate_trusted_overall(
        overall,
        scores,
        feature_confidences=high_conf,
        analysis_confidence=analysis_confidence,
        quality_warnings=warns,
        camera_angle="down_the_line",
    )
    return calibrated, scores


def test_nelly_live_dtl_overall_at_least_85() -> None:
    """CVM live 特征：DTL 转播 sanity 后 overall ≥ 85。"""
    overall, scores = _score_nelly(NELLY_LIVE)
    features, _ = sanitize_features(NELLY_LIVE, camera_angle="down_the_line")
    assert "top_wrist_position" not in features
    assert "left_arm_straightness" not in features
    assert "shoulder_rotation_top" not in features
    assert "tempo_ratio" not in features
    assert scores["downswing"] >= 85
    assert scores["impact"] >= 85
    assert overall >= 85


def test_nelly_snapshot_dtl_overall_at_least_85() -> None:
    overall, _ = _score_nelly(NELLY_SNAPSHOT, analysis_confidence=0.68)
    assert overall >= 85


def test_nelly_live_no_reverse_spine_or_chicken_wing() -> None:
    features, _ = sanitize_features(NELLY_LIVE, camera_angle="down_the_line")
    issues = diagnose_v2(features, phases=None, camera_angle="down_the_line")
    types = {i.type for i in issues}
    assert "reverse_spine" not in types
    assert "chicken_wing" not in types
    assert "early_extension" not in types


def test_nelly_live_top_phase_not_floor() -> None:
    features, _ = sanitize_features(NELLY_LIVE, camera_angle="down_the_line")
    top = score_phase(
        features, "top", club_category="iron", camera_angle="down_the_line"
    )
    assert top >= 50
