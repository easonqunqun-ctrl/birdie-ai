"""W6-T2：评分单测。"""

from __future__ import annotations

from app.pipeline.constants import FEATURES, PHASE_ORDER
from app.pipeline.scoring import (
    score_all_phases,
    score_feature,
    score_overall,
    score_phase,
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


def test_score_overall_club_category_none_equals_v1() -> None:
    """W22：不传 club_category → 与 V1 单套 PHASE_WEIGHTS 完全一致（向后兼容）。"""
    lopsided = {p: (100 if p == "downswing" else 0) for p in PHASE_ORDER}
    assert score_overall(lopsided, club_category=None) == score_overall(lopsided)


def test_score_overall_iron_equals_v1_gray_release_safe() -> None:
    """W22 灰度安全：iron 套 == V1 单套 → 7 铁报告分数接入前后不跳变。"""
    for scores in (
        {p: 80 for p in PHASE_ORDER},
        {p: (100 if p == "downswing" else 40) for p in PHASE_ORDER},
    ):
        assert score_overall(scores, club_category="iron") == score_overall(scores)


def test_score_overall_driver_emphasizes_downswing_backswing() -> None:
    """W22：driver 综合分对 backswing/downswing 更敏感、对 setup/impact 更不敏感。"""
    # 只有 downswing=100 其它 0：driver downswing 权重 0.29 > iron 0.25 → 综合更高
    down = {p: (100 if p == "downswing" else 0) for p in PHASE_ORDER}
    assert score_overall(down, club_category="driver") == 29
    assert score_overall(down, club_category="iron") == 25

    # 只有 setup=100 其它 0：driver setup 权重 0.11 < iron 0.15 → 综合更低
    setup = {p: (100 if p == "setup" else 0) for p in PHASE_ORDER}
    assert score_overall(setup, club_category="driver") == 11
    assert score_overall(setup, club_category="iron") == 15


def test_score_overall_putter_falls_back_to_v1() -> None:
    """putter 无专属相位权重 → V1 单套兜底（不抛错）。"""
    scores = {p: (100 if p == "impact" else 0) for p in PHASE_ORDER}
    assert score_overall(scores, club_category="putter") == score_overall(scores)


def test_score_phase_club_category_none_equals_v1() -> None:
    """W22 待办 #2：score_phase 不传 club_category → 与 V1 ideal 完全一致。"""
    features = {f["name"]: (f["ideal_min"] + f["ideal_max"]) / 2 for f in FEATURES}
    for phase in PHASE_ORDER:
        assert score_phase(features, phase, club_category=None) == score_phase(
            features, phase
        )


def test_score_phase_iron_equals_v1_gray_release_safe() -> None:
    """W22 灰度安全：iron 未 override 任何 ideal → 每个阶段分都 == V1。"""
    features = {f["name"]: (f["ideal_min"] + f["ideal_max"]) / 2 for f in FEATURES}
    # 再叠一组偏离值，确保不是因为都满分才相等
    features["shoulder_rotation_top"] = 98.0
    features["tempo_ratio"] = 2.0
    for phase in PHASE_ORDER:
        assert score_phase(features, phase, club_category="iron") == score_phase(
            features, phase
        )


def test_score_phase_driver_uses_category_ideal_band() -> None:
    """W22：driver override 了 shoulder_rotation_top 的 ideal 区间 → backswing 分数与 V1 不同。

    V1 ideal (30,95)，driver override (35,100)。取 value=98：V1 在区间外（线性衰减），
    driver 落入区间内（高分）→ 两者 backswing 阶段分必然不同。
    """
    features = {"shoulder_rotation_top": 98.0}
    v1 = score_phase(features, "backswing")
    driver = score_phase(features, "backswing", club_category="driver")
    assert driver != v1
    assert driver > v1  # 98 在 driver 区间内、V1 区间外 → driver 更高


def test_score_all_phases_threads_club_category() -> None:
    """score_all_phases 把 club_category 透传给 score_phase（driver 与默认在 backswing 不同）。"""
    features = {"shoulder_rotation_top": 98.0}
    default = score_all_phases(features)
    driver = score_all_phases(features, club_category="driver")
    assert driver["backswing"] != default["backswing"]
    # iron 仍与默认一致（灰度安全）
    iron = score_all_phases(features, club_category="iron")
    assert iron == default


def test_score_phase_camera_angle_threads_to_ideal() -> None:
    """W22 待办 #3：score_phase 收 camera_angle → top 阶段 ideal 走机位维。

    top_wrist_position 仅 dtl override(0.15,0.38)、V1 ideal 更宽；取 value=0.5
    （V1 区间内、dtl 区间外）→ dtl 与默认 top 阶段分不同。
    """
    features = {"top_wrist_position": 0.5}
    default = score_phase(features, "top")
    dtl = score_phase(features, "top", camera_angle="down_the_line")
    assert dtl != default


def test_score_overall_camera_angle_only_uses_angle_weights() -> None:
    """只传 camera_angle（category None）→ 综合分用机位维相位权重（iron delta 0）。"""
    from app.pipeline.angle_profiles import phase_weights_for

    phase_scores = {p: (100 if p == "downswing" else 0) for p in PHASE_ORDER}
    expected = int(round(100 * phase_weights_for("down_the_line")["downswing"]))
    assert (
        score_overall(phase_scores, camera_angle="down_the_line") == expected
    )


def test_score_all_phases_threads_camera_angle() -> None:
    """score_all_phases 把 camera_angle 透传给 score_phase。"""
    features = {"top_wrist_position": 0.5}
    default = score_all_phases(features)
    dtl = score_all_phases(features, camera_angle="down_the_line")
    assert dtl["top"] != default["top"]


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
