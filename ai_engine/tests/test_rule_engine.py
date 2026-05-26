"""P2-M7-10 · RuleEngine 单元测试。

覆盖 kickoff §3.2 / §3.3 / §3.4 / 互斥矩阵 / 严重度边界 / engine_version_tag。
"""

from __future__ import annotations

import pytest

from app.pipeline.rule_engine import (
    Rule,
    RuleCondition,
    RuleEngine,
    RuleResult,
    compute_severity,
    render_i18n_key,
)


# ============================================================
# helpers
# ============================================================


def _early_extension_rule():
    return Rule(
        name="early_extension",
        display_name_key="issues.early_extension.title",
        conditions=(
            RuleCondition(feature="hip_distance_to_setup", operator=">", threshold=0.15),
            RuleCondition(feature="spine_tilt_deg", operator="<", threshold=20.0),
        ),
        mutually_exclusive_with=("reverse_pivot",),
        confidence_floor=0.5,
    )


def _reverse_pivot_rule():
    return Rule(
        name="reverse_pivot",
        display_name_key="issues.reverse_pivot.title",
        conditions=(
            RuleCondition(feature="spine_tilt_deg", operator=">", threshold=10.0),
        ),
        mutually_exclusive_with=("early_extension",),
    )


def _chicken_wing_rule():
    return Rule(
        name="chicken_wing",
        display_name_key="issues.chicken_wing.title",
        conditions=(
            RuleCondition(feature="left_elbow_abduction_deg", operator=">", threshold=30.0),
        ),
    )


# ============================================================
# 1. RuleCondition evaluate
# ============================================================


@pytest.mark.parametrize(
    "operator,threshold,value,expected",
    [
        (">", 10, 11, True),
        (">", 10, 10, False),
        (">=", 10, 10, True),
        ("<", 10, 9, True),
        ("<=", 10, 10, True),
        ("==", 10, 10, True),
        ("==", 10, 11, False),
        ("!=", 10, 11, True),
    ],
)
def test_condition_evaluate_operators(operator, threshold, value, expected):
    cond = RuleCondition(feature="x", operator=operator, threshold=threshold)
    assert cond.evaluate({"x": value}) is expected


def test_condition_missing_feature_returns_false():
    cond = RuleCondition(feature="x", operator=">", threshold=10)
    assert cond.evaluate({"y": 100}) is False


def test_condition_type_error_returns_false():
    """字符串特征 vs 数值阈值 → 不抛错，返回 False。"""
    cond = RuleCondition(feature="x", operator=">", threshold=10)
    assert cond.evaluate({"x": "not_a_number"}) is False  # type: ignore[dict-item]


# ============================================================
# 2. Rule evaluate（AND 语义）
# ============================================================


def test_rule_evaluate_all_conditions_pass():
    rule = _early_extension_rule()
    features = {"hip_distance_to_setup": 0.20, "spine_tilt_deg": 15.0}
    assert rule.evaluate(features) is True


def test_rule_evaluate_one_condition_fails():
    rule = _early_extension_rule()
    features = {"hip_distance_to_setup": 0.10, "spine_tilt_deg": 15.0}
    assert rule.evaluate(features) is False


def test_rule_evaluate_empty_conditions_false():
    """空 conditions → False（防误触）。"""
    rule = Rule(name="x", display_name_key="x", conditions=())
    assert rule.evaluate({}) is False


def test_rule_get_severity_feature_explicit():
    rule = Rule(
        name="x",
        display_name_key="x",
        severity_feature="spine_tilt_deg",
        conditions=(RuleCondition("hip_distance_to_setup", ">", 0.15),),
    )
    assert rule.get_severity_feature() == "spine_tilt_deg"


def test_rule_get_severity_feature_defaults_first_condition():
    rule = _early_extension_rule()
    assert rule.get_severity_feature() == "hip_distance_to_setup"


# ============================================================
# 3. compute_severity（§3.3）
# ============================================================


def test_severity_just_at_threshold_is_zero():
    """ratio = (15 - 15) / 15 = 0 → 0.0"""
    rule = _early_extension_rule()
    features = {"hip_distance_to_setup": 0.15}
    assert compute_severity(rule, features) == 0.0


def test_severity_doubled_threshold_clamps_to_one():
    """ratio = (0.30 - 0.15) / 0.15 = 1.0 → clamp 1.0"""
    rule = _early_extension_rule()
    features = {"hip_distance_to_setup": 0.30}
    assert compute_severity(rule, features) == 1.0


def test_severity_over_doubled_threshold_still_one():
    rule = _early_extension_rule()
    features = {"hip_distance_to_setup": 0.50}
    assert compute_severity(rule, features) == 1.0


def test_severity_partial_offset():
    """ratio = (0.225 - 0.15) / 0.15 = 0.5"""
    rule = _early_extension_rule()
    features = {"hip_distance_to_setup": 0.225}
    assert abs(compute_severity(rule, features) - 0.5) < 1e-6


def test_severity_missing_feature_zero():
    rule = _early_extension_rule()
    assert compute_severity(rule, {}) == 0.0


def test_severity_zero_threshold_safe():
    rule = Rule(
        name="x",
        display_name_key="x",
        conditions=(RuleCondition("x", ">", 0.0),),
    )
    assert compute_severity(rule, {"x": 1.0}) == 1.0
    assert compute_severity(rule, {"x": 0.0}) == 0.0


# ============================================================
# 4. RuleEngine.diagnose（互斥 + 排序 + confidence_floor）
# ============================================================


def test_engine_diagnose_returns_triggered_rules():
    engine = RuleEngine(rules=[_chicken_wing_rule()])
    results = engine.diagnose({"left_elbow_abduction_deg": 35.0})
    assert len(results) == 1
    assert results[0].type == "chicken_wing"


def test_engine_diagnose_filters_untriggered_rules():
    engine = RuleEngine(rules=[_chicken_wing_rule()])
    results = engine.diagnose({"left_elbow_abduction_deg": 20.0})
    assert results == []


def test_engine_diagnose_applies_confidence_floor():
    """early_extension confidence_floor=0.5；confidence=0.3 应被过滤。"""
    engine = RuleEngine(rules=[_early_extension_rule()])
    features = {"hip_distance_to_setup": 0.25, "spine_tilt_deg": 10.0}
    results = engine.diagnose(features, confidences={"early_extension": 0.3})
    assert results == []


def test_engine_diagnose_passes_confidence_floor():
    engine = RuleEngine(rules=[_early_extension_rule()])
    features = {"hip_distance_to_setup": 0.25, "spine_tilt_deg": 10.0}
    results = engine.diagnose(features, confidences={"early_extension": 0.8})
    assert len(results) == 1
    assert results[0].confidence == 0.8


def test_engine_diagnose_mutual_exclusion_suppresses_lower_severity():
    """early_extension severity 高时应抑制 reverse_pivot（互斥）。"""
    engine = RuleEngine(rules=[_early_extension_rule(), _reverse_pivot_rule()])
    # 让 early_extension severity 高 (0.30 - 0.15)/0.15 = 1.0
    features = {"hip_distance_to_setup": 0.30, "spine_tilt_deg": 5.0}
    results = engine.diagnose(features, confidences={"early_extension": 1.0})
    types = [r.type for r in results]
    # early_extension trigger 成功 + spine_tilt_deg=5 < 10 reverse_pivot 不触发
    assert "early_extension" in types
    # 即使 reverse_pivot 触发也会被互斥（这里它本身就没触发）


def test_engine_diagnose_mutual_exclusion_both_trigger():
    """两条互斥规则都触发时，高 severity 胜出，低被抑制。"""
    rule_a = Rule(
        name="rule_a",
        display_name_key="x",
        conditions=(RuleCondition("x", ">", 10),),
        mutually_exclusive_with=("rule_b",),
    )
    rule_b = Rule(
        name="rule_b",
        display_name_key="x",
        conditions=(RuleCondition("y", ">", 10),),
        mutually_exclusive_with=("rule_a",),
    )
    engine = RuleEngine(rules=[rule_a, rule_b])
    # rule_a severity = (50-10)/10 = 4 → clamp 1.0
    # rule_b severity = (12-10)/10 = 0.2
    results = engine.diagnose({"x": 50, "y": 12})
    assert len(results) == 1
    assert results[0].type == "rule_a"  # 高 severity 胜出


def test_engine_diagnose_sorted_by_severity_desc():
    rule_a = Rule(
        name="rule_a",
        display_name_key="x",
        conditions=(RuleCondition("x", ">", 10),),
    )
    rule_b = Rule(
        name="rule_b",
        display_name_key="x",
        conditions=(RuleCondition("y", ">", 10),),
    )
    engine = RuleEngine(rules=[rule_a, rule_b])
    # rule_a severity=1.0 / rule_b severity=0.2
    results = engine.diagnose({"x": 50, "y": 12})
    assert [r.type for r in results] == ["rule_a", "rule_b"]


def test_engine_diagnose_payload_contains_used_features():
    engine = RuleEngine(rules=[_early_extension_rule()])
    features = {
        "hip_distance_to_setup": 0.25,
        "spine_tilt_deg": 10.0,
        "x_factor": 99.0,  # 与规则无关，不应出现在 payload
    }
    results = engine.diagnose(features, confidences={"early_extension": 0.9})
    assert results[0].payload == {
        "hip_distance_to_setup": 0.25,
        "spine_tilt_deg": 10.0,
    }
    assert "x_factor" not in results[0].payload


# ============================================================
# 5. 互斥矩阵对称性守门
# ============================================================


def test_mutual_exclusion_must_be_symmetric():
    bad_a = Rule(
        name="a",
        display_name_key="x",
        conditions=(RuleCondition("x", ">", 0),),
        mutually_exclusive_with=("b",),
    )
    bad_b = Rule(
        name="b",
        display_name_key="x",
        conditions=(RuleCondition("y", ">", 0),),
        # ↓ 故意不写 a，应被构造函数 reject
    )
    with pytest.raises(ValueError, match="symmetric"):
        RuleEngine(rules=[bad_a, bad_b])


def test_mutual_exclusion_target_outside_engine_ok():
    """互斥目标不在当前规则集 → 允许（W29-W33 规则陆续加入时是常态）。"""
    rule = Rule(
        name="a",
        display_name_key="x",
        conditions=(RuleCondition("x", ">", 0),),
        mutually_exclusive_with=("b_not_loaded_yet",),
    )
    # 不抛错
    engine = RuleEngine(rules=[rule])
    assert len(engine.rules) == 1


# ============================================================
# 6. engine_version_tag
# ============================================================


def test_engine_version_default_v2_0():
    rule = _chicken_wing_rule()
    engine = RuleEngine(rules=[rule])
    results = engine.diagnose({"left_elbow_abduction_deg": 35.0})
    assert results[0].rule_engine_version == "v2.0"


def test_rule_can_tag_v2_1():
    rule = Rule(
        name="future_rule",
        display_name_key="x",
        conditions=(RuleCondition("x", ">", 0),),
        engine_version_tag="v2.1",
    )
    engine = RuleEngine(rules=[rule])
    results = engine.diagnose({"x": 1.0})
    assert results[0].rule_engine_version == "v2.1"


# ============================================================
# 7. i18n 渲染（占位 → W33 真文案）
# ============================================================


def test_render_i18n_key_no_locale_returns_key_itself():
    """W28 起跑期无 locale_dict → 占位返回 key（不抛错）。"""
    assert (
        render_i18n_key("issues.early_extension.title", {"hip_dist": 0.21})
        == "issues.early_extension.title"
    )


def test_render_i18n_key_with_locale_dict_interpolates():
    locale = {"issues.early_extension.title": "你的髋部偏离 {hip_dist:.2f}m"}
    out = render_i18n_key(
        "issues.early_extension.title",
        {"hip_dist": 0.21},
        locale_dict=locale,
    )
    assert out == "你的髋部偏离 0.21m"


def test_render_i18n_key_missing_payload_falls_back():
    """模板有占位但 payload 缺 → 返回原模板（不抛错）。"""
    locale = {"x.y": "value={x}"}
    assert render_i18n_key("x.y", {}, locale_dict=locale) == "value={x}"


# ============================================================
# 8. RuleResult 字段
# ============================================================


def test_rule_result_carries_all_fields():
    engine = RuleEngine(rules=[_early_extension_rule()])
    features = {"hip_distance_to_setup": 0.30, "spine_tilt_deg": 10.0}
    results = engine.diagnose(features, confidences={"early_extension": 0.85})
    r = results[0]
    assert r.type == "early_extension"
    assert r.display_name_key == "issues.early_extension.title"
    assert r.confidence == 0.85
    assert r.severity == 1.0
    assert r.rule_engine_version == "v2.0"
    assert r.payload == {
        "hip_distance_to_setup": 0.30,
        "spine_tilt_deg": 10.0,
    }
