"""P2-M7-14 · run_real_analysis_v2 + diagnose_v2 单测。

仅覆盖**不依赖 mediapipe / 视频素材**的部分：
- ``diagnose_v2`` 把 YAML 触发的 RuleResult 渲染成 DiagnosedIssue（中文文案 + severity 折算）
- ``reset_caches`` 清理缓存后重新加载
- starter 集 confidence_floor + min_confidence 双过滤
"""

from __future__ import annotations

import pytest

from app.pipeline.real_pipeline_v2 import (
    _build_issue_from_rule_result,
    _severity_label,
    diagnose_v2,
    reset_caches,
)
from app.pipeline.rule_engine import (
    LOCALES_DIR,
    RULES_DIR,
    Rule,
    RuleCondition,
    RuleEngine,
    RuleResult,
    load_locale,
    load_rules_from_yaml,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_caches()


def test_severity_label_thresholds() -> None:
    assert _severity_label(0.0) == "low"
    assert _severity_label(0.29) == "low"
    assert _severity_label(0.3) == "medium"
    assert _severity_label(0.69) == "medium"
    assert _severity_label(0.7) == "high"
    assert _severity_label(1.0) == "high"


def test_build_issue_uses_locale_title_and_summary() -> None:
    locale = load_locale(LOCALES_DIR / "zh_CN.json")
    res = RuleResult(
        type="casting",
        severity=0.8,
        confidence=0.9,
        rule_engine_version="v2.0",
        display_name_key="issues.casting.title",
        payload={"wrist_release_timing": 0.30},
    )
    issue = _build_issue_from_rule_result(res, locale)
    assert issue.type == "casting"
    assert issue.severity == "high"
    assert issue.confidence == 0.9
    # description 来自 .summary key + payload 插值
    assert "30%" in issue.description


def test_build_issue_falls_back_to_v1_name_when_locale_missing() -> None:
    locale = {}  # 空 locale → render 走 key 本身；fallback_name=V1 中文名
    res = RuleResult(
        type="casting",
        severity=0.5,
        confidence=0.7,
        rule_engine_version="v2.0",
        display_name_key="issues.casting.title",
        payload={},
    )
    issue = _build_issue_from_rule_result(res, locale, fallback_name="抛杆（Casting）")
    assert issue.name == "抛杆（Casting）"


def test_diagnose_v2_triggers_casting_from_starter_yaml() -> None:
    issues = diagnose_v2(features={"wrist_release_timing": 0.30})
    types = [i.type for i in issues]
    assert "casting" in types
    casting = next(i for i in issues if i.type == "casting")
    assert "抛杆" in casting.name


def test_diagnose_v2_applies_mutual_exclusion() -> None:
    """early_extension 与 loss_of_posture 互斥；前者 severity 更高时后者被抑制。"""
    # spine_angle_impact_delta=20 → early_extension severity=(20-8)/8=1.5→1.0
    # head_lateral_shift=0.10 → loss_of_posture 也触发，但 severity 较低
    issues = diagnose_v2(
        features={
            "spine_angle_impact_delta": 20.0,
            "head_lateral_shift": 0.10,
        },
    )
    types = [i.type for i in issues]
    assert "early_extension" in types
    assert "loss_of_posture" not in types


def test_diagnose_v2_filters_below_min_confidence() -> None:
    # casting confidence_floor=0.6；显式给 0.3 应被 RuleEngine 过滤
    issues = diagnose_v2(
        features={"wrist_release_timing": 0.30},
        confidences={"casting": 0.3, "early_extension": 1.0,
                     "loss_of_posture": 1.0, "over_rotation": 1.0,
                     "under_rotation": 1.0},
    )
    assert all(i.type != "casting" for i in issues)


def test_diagnose_v2_accepts_custom_engine() -> None:
    """允许测试 / 灰度路径注入自己的 RuleEngine（替换 YAML 全集）。"""
    custom_rule = Rule(
        name="x",
        display_name_key="issues.casting.title",  # 复用 locale 文案
        conditions=(RuleCondition(feature="x", operator=">", threshold=10),),
    )
    engine = RuleEngine(rules=[custom_rule])
    issues = diagnose_v2(
        features={"x": 50},
        engine=engine,
        locale={"issues.casting.title": "自定义诊断", "issues.casting.summary": "x={x}"},
    )
    assert len(issues) == 1
    assert issues[0].type == "x"
    assert issues[0].name == "自定义诊断"


def test_reset_caches_reloads_yaml() -> None:
    # 触发缓存
    diagnose_v2(features={"wrist_release_timing": 0.30})
    # reset 后再调，仍能正常运行（隐式验证 reload 路径无副作用）
    reset_caches()
    issues = diagnose_v2(features={"wrist_release_timing": 0.20})
    assert any(i.type == "casting" for i in issues)


def test_starter_rules_loaded_into_engine_is_exactly_five() -> None:
    rules = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    engine = RuleEngine(rules=rules)
    assert len(engine.rules) == 5
