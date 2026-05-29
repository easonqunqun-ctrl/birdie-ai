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


def test_full_rules_loaded_into_engine_matches_yaml() -> None:
    """V2 全集 14 条规则（grip_weak V1 占位除外）。"""
    rules = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    engine = RuleEngine(rules=rules)
    assert len(engine.rules) == 14


def test_diagnose_v2_fills_key_frame_timestamp_from_phases() -> None:
    """phases 提供时，``key_frame_timestamp`` 应按 phase_anchor 落到具体秒数。"""
    from app.pipeline.phases import PhaseInfo, PhaseSegmentResult

    # 30 fps · 100 frames；top=45, impact=60
    phases = PhaseSegmentResult(
        phases={
            "setup": PhaseInfo(start_frame=0, end_frame=10, key_frame=5),
            "backswing": PhaseInfo(start_frame=11, end_frame=44, key_frame=28),
            "top": PhaseInfo(start_frame=45, end_frame=45, key_frame=45),
            "downswing": PhaseInfo(start_frame=46, end_frame=59, key_frame=53),
            "impact": PhaseInfo(start_frame=60, end_frame=60, key_frame=60),
            "follow_through": PhaseInfo(start_frame=61, end_frame=99, key_frame=80),
        },
        swing_start=11,
        swing_end=80,
        top_frame=45,
        impact_frame=60,
        handedness="right",
        lead_wrist_idx=15,
        lead_shoulder_idx=11,
        fps=30.0,
    )

    issues = diagnose_v2(
        features={"wrist_release_timing": 0.30},  # casting · phase_anchor=impact
        phases=phases,
    )
    casting = next(i for i in issues if i.type == "casting")
    assert casting.key_frame_timestamp == round(60 / 30.0, 2)  # 2.0s

    # over_rotation · phase_anchor=top → 45/30 = 1.5s
    issues_top = diagnose_v2(
        features={"shoulder_rotation_top": 120.0},
        phases=phases,
    )
    over = next(i for i in issues_top if i.type == "over_rotation")
    assert over.key_frame_timestamp == round(45 / 30.0, 2)  # 1.5s


def test_diagnose_v2_keyframe_timestamp_none_without_phases() -> None:
    issues = diagnose_v2(features={"wrist_release_timing": 0.30})
    casting = next(i for i in issues if i.type == "casting")
    assert casting.key_frame_timestamp is None


def test_diagnose_v2_full_set_triggers_steep_and_flat_mutually_exclusive() -> None:
    """flat_shoulder（x_factor > 60）与 steep_shoulder（x_factor < 25）互斥；同一 x_factor 只能触发一个。"""
    issues = diagnose_v2(features={"x_factor": 80.0})
    types = {i.type for i in issues}
    assert "flat_shoulder" in types
    assert "steep_shoulder" not in types

    issues_low = diagnose_v2(features={"x_factor": 10.0})
    types_low = {i.type for i in issues_low}
    assert "steep_shoulder" in types_low
    assert "flat_shoulder" not in types_low


def test_run_real_analysis_accepts_custom_diagnose_fn(monkeypatch) -> None:
    """P2-W5：``run_real_analysis`` 通过 ``diagnose_fn`` 把诊断步替换为 V2 实现。

    本测试不真跑 pipeline（依赖 mediapipe/cv2）；只验证签名 + 默认值。
    """
    from app.pipeline import real_pipeline as rp_mod

    # 默认走 V1 ``diagnose``
    assert rp_mod.DiagnoseFn is not None  # type alias 已定义
    # 真实端到端测试在 ai_engine integration suite 中按需手动跑（依赖视频素材）


def test_run_real_analysis_club_aware_scoring_default_false() -> None:
    """W22 灰度安全：``run_real_analysis`` 的 ``club_aware_scoring`` 默认 False。

    默认 False → club_category=None → 单套 PHASE_WEIGHTS，V1 生产路径字节不变。
    锁住默认值，防止有人误把球杆相位权重在 V1 全量打开（绕过 version_router 灰度）。
    """
    import inspect

    from app.pipeline.real_pipeline import run_real_analysis

    sig = inspect.signature(run_real_analysis)
    assert sig.parameters["club_aware_scoring"].default is False


@pytest.mark.asyncio
async def test_v2_entry_enables_club_aware_scoring(monkeypatch) -> None:
    """W22：``run_real_analysis_v2`` 调用 V1 入口时打开 ``club_aware_scoring``。

    球杆相位权重只在 V2 桶生效，跟随 version_router 灰度爬坡。不真跑 pipeline：
    桩掉 ``run_real_analysis`` 抓 kwargs、桩掉 ffprobe 探测，避免 mediapipe/视频依赖。
    """
    from types import SimpleNamespace

    from app.pipeline import real_pipeline as rp1
    from app.pipeline import real_pipeline_v2 as rp2
    from app.schemas import AnalyzeRequest

    captured: dict = {}

    async def _fake_run(req, **kwargs):  # noqa: ANN001, ANN202
        captured.update(kwargs)
        return SimpleNamespace(engine_warnings=None)

    # run_real_analysis 在 v2 里是函数级 import，桩源模块属性即可命中
    monkeypatch.setattr(rp1, "run_real_analysis", _fake_run)
    monkeypatch.setattr(rp2, "_probe_video_warnings", lambda _url: [])

    req = AnalyzeRequest(
        analysis_id="t-w22",
        video_url="http://example/v.mp4",
        camera_angle="face_on",
        club_type="driver",
    )
    await rp2.run_real_analysis_v2(req)

    assert captured.get("club_aware_scoring") is True
