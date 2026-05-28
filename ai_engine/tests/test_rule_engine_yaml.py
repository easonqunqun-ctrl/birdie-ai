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


def test_starter_yaml_loads_and_builds_engine() -> None:
    rules = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    assert len(rules) == 5
    names = {r.name for r in rules}
    assert names == {
        "early_extension",
        "loss_of_posture",
        "casting",
        "over_rotation",
        "under_rotation",
    }
    # 互斥矩阵对称性由 RuleEngine 构造时校验；不抛即对称
    engine = RuleEngine(rules=rules)
    assert engine.engine_version == "v2.0"


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
    """starter 集里 early_extension ↔ loss_of_posture / over ↔ under_rotation 双向声明。"""
    rules = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    by_name = {r.name: r for r in rules}
    assert "loss_of_posture" in by_name["early_extension"].mutually_exclusive_with
    assert "early_extension" in by_name["loss_of_posture"].mutually_exclusive_with
    assert "under_rotation" in by_name["over_rotation"].mutually_exclusive_with
    assert "over_rotation" in by_name["under_rotation"].mutually_exclusive_with
