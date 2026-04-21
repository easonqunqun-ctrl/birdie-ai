"""W6-T2：评分单测。"""

from __future__ import annotations

from app.pipeline.constants import FEATURES, PHASE_ORDER
from app.pipeline.scoring import (
    score_all_phases,
    score_feature,
    score_overall,
    weakest_phase,
)


def test_score_feature_ideal_center() -> None:
    """值落在理想区间中点 → 满分 100。"""
    assert score_feature(30, 25, 35) == 100


def test_score_feature_ideal_edge() -> None:
    """值在理想区间边界 → 85。"""
    assert score_feature(25, 25, 35) == 85
    assert score_feature(35, 25, 35) == 85


def test_score_feature_outside_tolerance() -> None:
    """超出容忍范围 → 0。"""
    # 默认 tolerance=0.5，区间宽 10，容忍边界是 ±5
    assert score_feature(45, 25, 35, tolerance=0.5) == 0
    assert score_feature(15, 25, 35, tolerance=0.5) == 0


def test_score_feature_within_tolerance() -> None:
    """在容忍范围内但超出理想 → 0-84。"""
    s = score_feature(38, 25, 35, tolerance=0.5)
    # 偏离 3/10 = 0.3；占容忍 60% → 84*(1-0.6)=33.6 ≈ 34
    assert 0 < s < 85


def test_score_phase_with_ideal_features() -> None:
    """构造一组"所有特征都在 ideal 中点"的假输入，阶段分应接近 100。"""
    features = {
        f["name"]: (f["ideal_min"] + f["ideal_max"]) / 2 for f in FEATURES
    }
    scores = score_all_phases(features)
    for phase, s in scores.items():
        assert 95 <= s <= 100, f"phase {phase} 分数 {s} 偏低"


def test_score_overall_weighted_mean() -> None:
    """综合分 = 阶段分的 PHASE_WEIGHTS 加权均值。"""
    phase_scores = {p: 80 for p in PHASE_ORDER}
    assert score_overall(phase_scores) == 80

    # 只有 downswing=100，其它 0；downswing 权重 0.25 → 综合 25
    lopsided = {p: (100 if p == "downswing" else 0) for p in PHASE_ORDER}
    assert score_overall(lopsided) == 25


def test_weakest_phase_returns_lowest() -> None:
    scores = {
        "setup": 90,
        "backswing": 85,
        "top": 78,
        "downswing": 60,
        "impact": 75,
        "follow_through": 85,
    }
    assert weakest_phase(scores) == "downswing"


def test_weakest_phase_tie_breaker_uses_phase_order() -> None:
    """多阶段并列最低时，按 PHASE_ORDER 取最靠前那个。"""
    scores = {p: 70 for p in PHASE_ORDER}
    assert weakest_phase(scores) == "setup"
