"""P2-M7-06 · 置信度三层公式单元测试。

覆盖 kickoff §3.2.1 / §3.2.2 / §3.2.3 公式 + §3.3 档位边界。
"""

from __future__ import annotations

import pytest

from app.pipeline.confidence import (
    ANALYSIS_HIGH_THRESHOLD,
    ANALYSIS_LOW_THRESHOLD,
    ANGLE_HARD_OFFSET_DEG,
    ISSUE_CONFIRMED_THRESHOLD,
    ISSUE_LEANING_THRESHOLD,
    PER_WARNING_PENALTY,
    V1_DEFAULT_ANALYSIS_CONFIDENCE,
    analysis_tier,
    build_analysis_breakdown,
    build_feature_breakdown,
    build_issue_breakdown,
    compute_analysis_confidence,
    feature_confidence,
    issue_confidence,
    issue_tier,
    should_recommend_retake,
)


# ============================================================
# Layer 1：feature_confidence
# ============================================================


def test_feature_confidence_empty_returns_zero():
    assert feature_confidence(None) == 0.0
    assert feature_confidence([]) == 0.0
    assert feature_confidence([[]]) == 0.0


def test_feature_confidence_all_high():
    # 3 帧 × 4 关键点，全部 0.9 → mean=0.9, vfr=1.0 → 0.9
    sub = [[0.9] * 4 for _ in range(3)]
    assert abs(feature_confidence(sub) - 0.9) < 1e-6


def test_feature_confidence_all_low_visibility():
    # mean=0.3, per_frame_mean=0.3 < 0.5 → vfr=0 → conf=0
    sub = [[0.3] * 4 for _ in range(3)]
    assert feature_confidence(sub) == 0.0


def test_feature_confidence_mixed_frames():
    # 2 帧高 + 1 帧低 → mean=(0.8*2*4+0.3*4)/(3*4)= (6.4+1.2)/12=0.6333
    # vfr = 2/3
    sub = [[0.8] * 4, [0.8] * 4, [0.3] * 4]
    expected = (6.4 + 1.2) / 12 * (2 / 3)
    assert abs(feature_confidence(sub) - expected) < 1e-6


def test_feature_confidence_clamps_to_01():
    # 不可能 > 1.0
    sub = [[1.5] * 4 for _ in range(3)]
    assert feature_confidence(sub) == 1.0


def test_build_feature_breakdown_returns_all_components():
    sub = [[0.9] * 4 for _ in range(3)]
    bd = build_feature_breakdown("spine_angle_setup", sub)
    assert bd.feature_name == "spine_angle_setup"
    assert abs(bd.mean_visibility - 0.9) < 1e-6
    assert bd.valid_frame_ratio == 1.0
    assert abs(bd.confidence - 0.9) < 1e-6


def test_build_feature_breakdown_empty_safe():
    bd = build_feature_breakdown("x_factor", None)
    assert bd.confidence == 0.0
    assert bd.mean_visibility == 0.0


# ============================================================
# Layer 2：issue_confidence + tier
# ============================================================


def test_issue_confidence_empty_features_returns_zero():
    assert issue_confidence([]) == 0.0


def test_issue_confidence_high_features_zero_distance():
    # feat_avg=0.9, sigmoid(0)=0.5 → 0.5+0.25=0.75 → 0.9*0.75=0.675
    out = issue_confidence([0.9, 0.9, 0.9], threshold_distance=0.0)
    assert abs(out - 0.675) < 1e-3


def test_issue_confidence_increases_with_threshold_distance():
    low = issue_confidence([0.8, 0.8], threshold_distance=0.0)
    mid = issue_confidence([0.8, 0.8], threshold_distance=2.0)
    high = issue_confidence([0.8, 0.8], threshold_distance=5.0)
    assert low < mid < high


def test_issue_tier_boundaries():
    # >0.85 confirmed
    assert issue_tier(0.86) == "confirmed"
    # 0.6 边界 inclusive
    assert issue_tier(0.6) == "leaning"
    assert issue_tier(0.85) == "leaning"
    # <0.6 hidden
    assert issue_tier(0.59) == "hidden"
    assert issue_tier(0.0) == "hidden"


def test_build_issue_breakdown_complete():
    bd = build_issue_breakdown("casting", [0.9, 0.9], threshold_distance=3.0)
    assert bd.issue_type == "casting"
    assert bd.feature_avg == 0.9
    assert bd.threshold_distance == 3.0
    assert bd.tier in ("confirmed", "leaning", "hidden")


# ============================================================
# Layer 3：compute_analysis_confidence（kickoff §3.2.3 典型值表）
# ============================================================


def test_analysis_confidence_standard_indoor_tripod():
    """kickoff §3.2.3 行 1：标准光线室内三脚架 → ~0.81 高"""
    out = compute_analysis_confidence(
        mean_visibility=0.92,
        quality_warnings=[],
        camera_angle_offset_deg=0.0,
        feature_confidences={"spine": 0.88, "x_factor": 0.88, "tempo": 0.88},
    )
    # 0.92 * 1.0 * 1.0 * 0.88 = 0.8096
    assert abs(out - 0.8096) < 1e-3
    assert out >= ANALYSIS_HIGH_THRESHOLD


def test_analysis_confidence_low_light_shake():
    """kickoff §3.2.3 行 2：略暗光 + 轻微抖动 → ~0.39 低"""
    out = compute_analysis_confidence(
        mean_visibility=0.78,
        quality_warnings=["low_light", "camera_shake"],
        camera_angle_offset_deg=0.0,
        feature_confidences={"spine": 0.72, "x_factor": 0.72, "tempo": 0.72},
    )
    # base=0.78, qw=1.0-0.15*2=0.7, angle=1.0, feat_avg=0.72
    # 0.78*0.7*1.0*0.72 = 0.3931
    assert abs(out - 0.3931) < 1e-3
    assert out < ANALYSIS_LOW_THRESHOLD
    assert should_recommend_retake(out)


def test_analysis_confidence_offset_20_deg():
    """kickoff §3.2.3 行 3：偏角 20° + 正常光 → ~0.27 低"""
    out = compute_analysis_confidence(
        mean_visibility=0.85,
        quality_warnings=[],
        camera_angle_offset_deg=20.0,
        feature_confidences={"spine": 0.80, "x_factor": 0.80, "tempo": 0.80},
    )
    # base=0.85, qw=1.0, angle=0.4 (>15°), feat_avg=0.80
    # 0.85*1.0*0.4*0.80 = 0.272
    assert abs(out - 0.272) < 1e-3
    assert out < ANALYSIS_LOW_THRESHOLD


def test_analysis_confidence_handles_none_offset():
    out = compute_analysis_confidence(
        mean_visibility=0.9,
        quality_warnings=None,
        camera_angle_offset_deg=None,
        feature_confidences=None,
    )
    assert out == 0.9  # base * 1.0 * 1.0 * 1.0


def test_analysis_confidence_no_feature_confidences_defaults_to_one():
    out = compute_analysis_confidence(
        mean_visibility=0.9,
        quality_warnings=[],
        camera_angle_offset_deg=0.0,
        feature_confidences={},
    )
    assert out == 0.9


def test_analysis_confidence_negative_offset_uses_abs():
    out = compute_analysis_confidence(
        mean_visibility=0.85,
        quality_warnings=[],
        camera_angle_offset_deg=-20.0,
        feature_confidences={"x": 0.80},
    )
    # abs(-20)=20 > 15 → angle=0.4
    assert abs(out - (0.85 * 1.0 * 0.4 * 0.80)) < 1e-3


def test_analysis_confidence_many_warnings_clamped_to_zero():
    """warn_count * 0.15 可能 > 1.0；penalty 应被 max(0, ...) 兜底。"""
    out = compute_analysis_confidence(
        mean_visibility=0.9,
        quality_warnings=["a", "b", "c", "d", "e", "f", "g"],  # 7 → penalty would be 1-1.05=-0.05
        camera_angle_offset_deg=0.0,
        feature_confidences={"x": 0.9},
    )
    assert out == 0.0


def test_analysis_tier_boundaries():
    assert analysis_tier(0.75) == "high"
    assert analysis_tier(0.749) == "medium"
    assert analysis_tier(0.5) == "medium"
    assert analysis_tier(0.499) == "low"
    assert analysis_tier(0.0) == "low"


def test_should_recommend_retake_only_low_tier():
    assert should_recommend_retake(0.49) is True
    assert should_recommend_retake(0.5) is False
    assert should_recommend_retake(0.8) is False


def test_build_analysis_breakdown_carries_intermediate_values():
    bd = build_analysis_breakdown(
        mean_visibility=0.78,
        quality_warnings=["low_light", "camera_shake"],
        camera_angle_offset_deg=0.0,
        feature_confidences={"spine": 0.72},
    )
    assert bd.base == 0.78
    assert abs(bd.quality_warning_penalty - 0.7) < 1e-6
    assert bd.angle_penalty == 1.0
    assert bd.feature_avg == 0.72
    assert bd.tier == "low"
    assert bd.recommend_retake is True


# ============================================================
# V1 兜底（kickoff §4.3）
# ============================================================


def test_v1_default_confidence_constant_is_one():
    assert V1_DEFAULT_ANALYSIS_CONFIDENCE == 1.0


# ============================================================
# 边界
# ============================================================


def test_nan_visibility_treated_as_zero():
    nan = float("nan")
    out = compute_analysis_confidence(
        mean_visibility=nan,
        quality_warnings=[],
        camera_angle_offset_deg=0.0,
        feature_confidences={"x": 1.0},
    )
    assert out == 0.0


def test_threshold_constants_match_kickoff():
    """守门：阈值必须与 kickoff §3.2.2 / §3.3 一致。"""
    assert ISSUE_CONFIRMED_THRESHOLD == 0.85
    assert ISSUE_LEANING_THRESHOLD == 0.60
    assert ANALYSIS_HIGH_THRESHOLD == 0.75
    assert ANALYSIS_LOW_THRESHOLD == 0.50
    assert ANGLE_HARD_OFFSET_DEG == 15.0
    assert PER_WARNING_PENALTY == 0.15
