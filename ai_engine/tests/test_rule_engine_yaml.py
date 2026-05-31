"""P2-W4 · RuleEngine YAML loader + locale 集成测试。

覆盖：
- YAML loader 解析 + schema 校验（缺字段 / 非法 operator / 未知字段）
- starter rules 全集可加载 + 互斥矩阵对称（构造 engine 不抛错）
- locale loader → render_i18n_key 端到端：starter rule trigger 后能拿到中文文案
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.pipeline.rule_engine import (
    LOCALES_DIR,
    RULES_DIR,
    RuleEngine,
    _coerce_rule,
    load_locale,
    load_rules_from_yaml,
    render_i18n_key,
)


EXPECTED_V2_RULES = {
    "early_extension",
    "loss_of_posture",
    "casting",
    "over_rotation",
    "under_rotation",
    "over_the_top",
    "sway_slide",
    "reverse_spine",
    "chicken_wing",
    "sway_lead",
    "hanging_back",
    "flat_shoulder",
    "steep_shoulder",
    "open_stance",
}


def test_starter_yaml_loads_and_builds_engine() -> None:
    rules = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    assert len(rules) == len(EXPECTED_V2_RULES)
    assert {r.name for r in rules} == EXPECTED_V2_RULES
    # 互斥矩阵对称性由 RuleEngine 构造时校验；不抛即对称
    engine = RuleEngine(rules=rules)
    assert engine.engine_version == "v2.0"


def test_full_rule_set_covers_v1_diagnose_types() -> None:
    """V2 全集应覆盖 V1 ``diagnose._RULES`` 全部 issue 类型；``grip_weak`` 占位除外。"""
    from app.pipeline.diagnose import _RULES as v1_rules

    v1_types = set()
    for fn in v1_rules:
        # 函数名 ``_rule_xxx`` → issue_type ``xxx``
        name = fn.__name__.removeprefix("_rule_")
        v1_types.add(name)
    v1_types.discard("grip_weak")  # V1 占位，不迁入 YAML

    rules = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    yaml_types = {r.name for r in rules}
    missing = v1_types - yaml_types
    assert not missing, f"V2 YAML 缺以下 V1 规则：{sorted(missing)}"


def test_starter_yaml_rules_have_locale_entries() -> None:
    rules = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    locale = load_locale(LOCALES_DIR / "zh_CN.json")
    for rule in rules:
        assert rule.display_name_key in locale, f"locale 缺 key={rule.display_name_key}"


def test_render_i18n_key_with_starter_locale_interpolates() -> None:
    locale = load_locale(LOCALES_DIR / "zh_CN.json")
    out = render_i18n_key(
        "issues.casting.summary",
        {"wrist_release_timing": 0.35},
        locale_dict=locale,
    )
    assert "35%" in out
    assert "理想 50%-70%" in out


def test_end_to_end_yaml_trigger_and_render() -> None:
    rules = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    locale = load_locale(LOCALES_DIR / "zh_CN.json")
    engine = RuleEngine(rules=rules)
    # 触发 casting：wrist_release_timing < 0.40
    results = engine.diagnose(
        {"wrist_release_timing": 0.30},
        confidences={"casting": 0.85},
    )
    assert len(results) == 1
    r = results[0]
    assert r.type == "casting"
    rendered_title = render_i18n_key(r.display_name_key, r.payload, locale_dict=locale)
    assert rendered_title == "抛杆（Casting）"
    rendered_summary = render_i18n_key(
        "issues.casting.summary", r.payload, locale_dict=locale
    )
    assert "30%" in rendered_summary


def test_coerce_rule_rejects_unknown_field() -> None:
    raw = {
        "name": "x",
        "display_name_key": "x",
        "extra_unknown_field": True,
        "conditions": [{"feature": "x", "operator": ">", "threshold": 0}],
    }
    with pytest.raises(ValueError, match="未知字段"):
        _coerce_rule(raw)


def test_coerce_rule_rejects_invalid_operator() -> None:
    raw = {
        "name": "x",
        "display_name_key": "x",
        "conditions": [{"feature": "x", "operator": "===", "threshold": 0}],
    }
    with pytest.raises(ValueError, match="operator"):
        _coerce_rule(raw)


def test_coerce_rule_rejects_empty_conditions() -> None:
    raw = {
        "name": "x",
        "display_name_key": "x",
        "conditions": [],
    }
    with pytest.raises(ValueError, match="non.?empty|非空"):
        _coerce_rule(raw)


def test_load_rules_from_yaml_handles_inline_string(tmp_path: Path) -> None:
    yaml_path = tmp_path / "tiny.yaml"
    yaml_path.write_text(
        """
version: v2.0
rules:
  - name: tiny_rule
    display_name_key: tiny.title
    conditions:
      - feature: foo
        operator: ">="
        threshold: 1.5
""",
        encoding="utf-8",
    )
    rules = load_rules_from_yaml(yaml_path)
    assert len(rules) == 1
    assert rules[0].conditions[0].operator == ">="
    assert rules[0].conditions[0].threshold == 1.5


def test_starter_mutual_exclusion_is_symmetric() -> None:
    """V2 全集互斥矩阵双向声明。"""
    rules = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    by_name = {r.name: r for r in rules}
    assert "loss_of_posture" in by_name["early_extension"].mutually_exclusive_with
    assert "early_extension" in by_name["loss_of_posture"].mutually_exclusive_with
    assert "under_rotation" in by_name["over_rotation"].mutually_exclusive_with
    assert "over_rotation" in by_name["under_rotation"].mutually_exclusive_with
    assert "steep_shoulder" in by_name["flat_shoulder"].mutually_exclusive_with
    assert "flat_shoulder" in by_name["steep_shoulder"].mutually_exclusive_with
    assert "sway_slide" in by_name["loss_of_posture"].mutually_exclusive_with
    assert "loss_of_posture" in by_name["sway_slide"].mutually_exclusive_with


def test_every_rule_has_phase_anchor_and_locale_summary() -> None:
    """全集每条规则的 phase_anchor 合法，且 locale 同时存在 title + summary。"""
    valid_anchors = {"setup", "backswing", "top", "downswing", "impact", "follow_through"}
    rules = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    locale = load_locale(LOCALES_DIR / "zh_CN.json")
    for rule in rules:
        assert rule.phase_anchor in valid_anchors, rule.name
        assert rule.display_name_key in locale
        summary_key = rule.display_name_key.replace(".title", ".summary")
        assert summary_key in locale, f"locale 缺 summary key={summary_key}"
        if rule.name in (
            "over_rotation",
            "under_rotation",
            "flat_shoulder",
            "steep_shoulder",
        ):
            safe_key = summary_key + "_safe"
            assert safe_key in locale, f"locale 缺 A6 safe key={safe_key}"


def test_coerce_rule_rejects_invalid_phase_anchor() -> None:
    raw = {
        "name": "x",
        "display_name_key": "x",
        "phase_anchor": "not_a_phase",
        "conditions": [{"feature": "x", "operator": ">", "threshold": 0}],
    }
    with pytest.raises(ValueError, match="phase_anchor"):
        _coerce_rule(raw)
