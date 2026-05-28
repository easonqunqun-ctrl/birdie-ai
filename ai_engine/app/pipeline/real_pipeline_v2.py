"""P2-M7-14 · V2 分析管线骨架（灰度可独立切换）。

设计要点
--------
- **复用 V1 大部分链路**（preprocess / pose / phases / features / scoring /
  recommend / 衍生产物）；本 PR 仅完成 **V2 路由打通** + 暴露 ``diagnose_v2``
  公共 API，方便 W34 接 P2-M7-02 / P2-M7-06 后无缝替换诊断与置信度填充。
- **降级安全**：YAML 加载失败 / V2 入口抛错 → fallback 到 V1 ``run_real_analysis``；
  线上日志打 ``v2_resources_unavailable_falling_back_to_v1`` 便于复盘。
- 报告 ``engine_version`` 字段由 ``main.py`` 在路由层最终覆盖；本模块内部不显式
  写值，避免与路由层重复。

P2-W5 收口
----------
- ✅ ``run_real_analysis_v2`` 通过 ``diagnose_fn=diagnose_v2`` 真正重诊 issues
- ✅ ``diagnose_v2`` 接受 ``PhaseSegmentResult`` 并填 ``key_frame_timestamp``
- ✅ YAML 全集 14 条规则覆盖 V1 全部 issue（``grip_weak`` 占位除外）

后续 W34 接力
-------------
- 接 P2-M7-02 → 填 ``AnalyzeResult.engine_warnings``
- 接 P2-M7-06 → 填 ``IssueItem.confidence`` / ``analysis_confidence``
"""

from __future__ import annotations

import logging

from app.pipeline.constants import issue_meta
from app.pipeline.diagnose import (
    DiagnosedIssue,
    MAX_ISSUES,
    MIN_DISPLAY_CONFIDENCE,
)
from app.pipeline.phases import PhaseSegmentResult
from app.pipeline.rule_engine import (
    LOCALES_DIR,
    RULES_DIR,
    Rule,
    RuleEngine,
    RuleResult,
    load_locale,
    load_rules_from_yaml,
    render_i18n_key,
)
from app.schemas import AnalyzeRequest, AnalyzeResult

log = logging.getLogger("ai_engine.real_pipeline_v2")


# 进程级缓存：避免每次请求都 IO 读 YAML / JSON
_RULES_CACHE: list[Rule] | None = None
_LOCALE_CACHE: dict[str, str] | None = None


def _get_rules() -> list[Rule]:
    global _RULES_CACHE
    if _RULES_CACHE is None:
        _RULES_CACHE = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    return _RULES_CACHE


def _get_locale() -> dict[str, str]:
    global _LOCALE_CACHE
    if _LOCALE_CACHE is None:
        _LOCALE_CACHE = load_locale(LOCALES_DIR / "zh_CN.json")
    return _LOCALE_CACHE


def reset_caches() -> None:
    """单测 / 热更新 / 配置回滚时清缓存。"""
    global _RULES_CACHE, _LOCALE_CACHE
    _RULES_CACHE = None
    _LOCALE_CACHE = None


def _severity_label(ratio: float) -> str:
    """将 0-1 severity ratio 折算成 V1 风格的 high/medium/low 标签。"""
    if ratio >= 0.7:
        return "high"
    if ratio >= 0.3:
        return "medium"
    return "low"


def _keyframe_timestamp(
    res: RuleResult, phases: PhaseSegmentResult | None
) -> float | None:
    """根据 ``phase_anchor`` 从 ``PhaseSegmentResult`` 计算关键帧秒数。

    优先级：top/impact → 用 ``top_frame`` / ``impact_frame``（与 V1 一致）；
    其余阶段 → 用对应 ``PhaseInfo.key_frame``。
    """
    if phases is None or phases.fps <= 0:
        return None
    anchor = res.phase_anchor
    if anchor == "top":
        frame = phases.top_frame
    elif anchor == "impact":
        frame = phases.impact_frame
    else:
        info = phases.phases.get(anchor)
        if info is None:
            return None
        frame = info.key_frame
    return round(frame / phases.fps, 2)


def _build_issue_from_rule_result(
    res: RuleResult,
    locale: dict[str, str],
    *,
    fallback_name: str | None = None,
    phases: PhaseSegmentResult | None = None,
) -> DiagnosedIssue:
    """RuleResult → DiagnosedIssue（沿用 V1 schema，便于 main.py 直接组装）。"""
    name = fallback_name or render_i18n_key(
        res.display_name_key, res.payload, locale_dict=locale
    )
    summary_key = res.display_name_key.replace(".title", ".summary")
    description = render_i18n_key(summary_key, res.payload, locale_dict=locale)
    return DiagnosedIssue(
        type=res.type,
        name=name,
        severity=_severity_label(res.severity),
        description=description,
        confidence=res.confidence,
        key_frame_timestamp=_keyframe_timestamp(res, phases),
        metrics=dict(res.payload),
    )


def diagnose_v2(
    features: dict[str, float],
    phases: PhaseSegmentResult | None = None,
    *,
    min_confidence: float = MIN_DISPLAY_CONFIDENCE,
    max_issues: int = MAX_ISSUES,
    engine: RuleEngine | None = None,
    locale: dict[str, str] | None = None,
    confidences: dict[str, float] | None = None,
) -> list[DiagnosedIssue]:
    """V2 诊断主入口：YAML 规则 + i18n locale → DiagnosedIssue。

    与 V1 ``diagnose`` 签名一致；report assembly 不需要分支。

    - ``confidences`` 缺省时所有规则置 1.0；W34 接 P2-M7-06 后由 issue_confidence 填充
    - ``phases`` 用于按 ``phase_anchor`` 填 ``key_frame_timestamp``；缺省时该字段为 None
    """
    rules_engine = engine or RuleEngine(rules=_get_rules())
    loc = locale if locale is not None else _get_locale()

    rule_confs = confidences or {r.name: 1.0 for r in rules_engine.rules}
    results = rules_engine.diagnose(features, confidences=rule_confs)

    issues: list[DiagnosedIssue] = []
    for res in results:
        try:
            fallback = issue_meta(res.type)["name"]
        except KeyError:
            fallback = None
        issue = _build_issue_from_rule_result(
            res, loc, fallback_name=fallback, phases=phases
        )
        if issue.confidence < min_confidence:
            continue
        issues.append(issue)

    return issues[:max_issues]


async def run_real_analysis_v2(req: AnalyzeRequest) -> AnalyzeResult:
    """V2 真实分析入口。

    P2-W5：通过 ``real_pipeline.run_real_analysis(diagnose_fn=diagnose_v2)`` 真正用
    YAML RuleEngine 重诊 issues；features 与 phases 由 V1 pipeline 计算后透传给
    ``diagnose_v2``。

    出错降级：V2 资源（YAML / locale）加载失败 → 记日志后退回 V1 ``diagnose``，
    确保灰度期不影响报告交付；V1 入口抛 PipelineError 时直接透传，由 main.py
    统一捕获转 ``status=failed``。
    """
    from app.pipeline.real_pipeline import run_real_analysis

    diagnose_impl = None
    try:
        _get_rules()
        _get_locale()
        diagnose_impl = diagnose_v2
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "v2_resources_unavailable_falling_back_to_v1",
            extra={"analysis_id": req.analysis_id, "err": repr(exc)},
        )

    return await run_real_analysis(req, diagnose_fn=diagnose_impl)


__all__ = [
    "diagnose_v2",
    "reset_caches",
    "run_real_analysis_v2",
]
