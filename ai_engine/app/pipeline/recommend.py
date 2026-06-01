"""W6-T2：issue → drill 推荐映射（docs/05 §3.4 · docs/14 附录 A.2）。

职责
----
给定诊断出的 issues 列表，查 `constants.ISSUE_DRILL_MAP`，组装成 `RecommendationItem`
列表，遵循以下规则：
1. 最多返回 `MAX_RECOMMENDATIONS_PER_ANALYSIS` 条（docs/01：3 条）
2. 同一个 drill_id 去重（多个 issue 指同一个 drill 时只保留一个，且关联到最严重那个 issue）
3. high severity 的 issue 优先取 2 个 drill；medium/low 取 1 个
4. drill 详情（name/steps/...）从 `DRILL_TEMPLATES` 查（mock_pipeline 里）

drill_id 未在 DRILL_TEMPLATES 登记时（理论上不会发生，constants 里是闭集）会跳过而非
崩溃，log 一条 warning 供 T2-drills 对齐排查。
"""

from __future__ import annotations

import logging

from app.pipeline.constants import (
    ISSUE_DRILL_MAP,
    MAX_RECOMMENDATIONS_PER_ANALYSIS,
    PHASE_LABELS,
)
from app.pipeline.diagnose import DiagnosedIssue
from app.schemas import RecommendationItem

log = logging.getLogger("ai_engine.recommend")

# 无命名 issue 时，按最弱阶段推荐基础练习
PHASE_WEAK_DRILL: dict[str, str] = {
    "setup": "drill_alignment_stick",
    "backswing": "drill_shoulder_turn",
    "top": "drill_backswing_stop",
    "downswing": "drill_half_swing",
    "impact": "drill_impact_bag",
    "follow_through": "drill_weight_shift",
}
LOW_SCORE_RECOMMEND_THRESHOLD = 65

# Drill 详情表：从 mock_pipeline 镜像（T2-drills 会把这份数据独立成 `drill_library.py`；
# 暂时这样 import，避免循环依赖写一层 getter）。
_DRILL_DETAILS_CACHE: dict[str, dict] | None = None


def _load_drill_details() -> dict[str, dict]:
    global _DRILL_DETAILS_CACHE
    if _DRILL_DETAILS_CACHE is not None:
        return _DRILL_DETAILS_CACHE
    from app.mock_pipeline import DRILL_TEMPLATES

    _DRILL_DETAILS_CACHE = {d["drill_id"]: d for d in DRILL_TEMPLATES}
    return _DRILL_DETAILS_CACHE


def recommend(
    issues: list[DiagnosedIssue],
    *,
    max_recommendations: int = MAX_RECOMMENDATIONS_PER_ANALYSIS,
) -> list[RecommendationItem]:
    """组装推荐列表。

    Args:
        issues: `diagnose` 输出，已按严重度排好序
        max_recommendations: 返回上限

    Returns:
        list[RecommendationItem]，长度 ≤ max_recommendations
    """
    drill_details = _load_drill_details()

    # 遍历 issue 决定要拿几个 drill：
    # - high  → 取该 issue 映射的全部 drill（最多 2）
    # - 其它  → 只取第一个 drill
    picked_ids: list[str] = []
    picked_by_drill: dict[str, str] = {}  # drill_id -> issue_type（首个被关联的 issue）
    for issue in issues:
        drills = ISSUE_DRILL_MAP.get(issue.type, [])
        if not drills:
            continue
        take = drills if issue.severity == "high" else drills[:1]
        for drill_id in take:
            if drill_id in picked_by_drill:
                continue  # 去重
            picked_ids.append(drill_id)
            picked_by_drill[drill_id] = issue.type
            if len(picked_ids) >= max_recommendations:
                break
        if len(picked_ids) >= max_recommendations:
            break

    recommendations: list[RecommendationItem] = []
    for drill_id in picked_ids:
        detail = drill_details.get(drill_id)
        if detail is None:
            log.warning(
                "drill_not_in_library",
                extra={"drill_id": drill_id, "issue_type": picked_by_drill[drill_id]},
            )
            continue
        # `target_issue` 覆写为"实际关联到的 issue"（多对一场景下用户才知道这条推荐是干啥的）
        recommendations.append(
            RecommendationItem(
                drill_id=detail["drill_id"],
                name=detail["name"],
                target_issue=picked_by_drill[drill_id],
                description=detail["description"],
                duration_minutes=detail["duration_minutes"],
                sets=detail["sets"],
                steps=detail["steps"],
            )
        )

    return recommendations


def recommend_with_phase_fallback(
    issues: list[DiagnosedIssue],
    *,
    phase_scores: dict[str, int] | None = None,
    overall_score: int | None = None,
    weakest_phase: str | None = None,
    max_recommendations: int = MAX_RECOMMENDATIONS_PER_ANALYSIS,
) -> list[RecommendationItem]:
    """issue 映射 drill；无 issue 且综合分偏低时按最弱阶段兜底 1 条练习。"""
    recs = recommend(issues, max_recommendations=max_recommendations)
    if recs or not phase_scores or not weakest_phase:
        return recs
    weak_score = int(phase_scores.get(weakest_phase, 100))
    if (
        overall_score is not None
        and overall_score >= LOW_SCORE_RECOMMEND_THRESHOLD
        and weak_score >= 55
    ):
        return recs

    drill_id = PHASE_WEAK_DRILL.get(weakest_phase, "drill_half_swing")
    drill_details = _load_drill_details()
    detail = drill_details.get(drill_id)
    if detail is None:
        log.warning("phase_fallback_drill_missing", extra={"drill_id": drill_id})
        return recs

    phase_label = PHASE_LABELS.get(weakest_phase, weakest_phase)
    return [
        RecommendationItem(
            drill_id=detail["drill_id"],
            name=detail["name"],
            target_issue=f"weak_{weakest_phase}",
            description=(
                f"本次「{phase_label}」相对最弱（{weak_score} 分），"
                f"建议优先练习：{detail['description']}"
            ),
            duration_minutes=detail["duration_minutes"],
            sets=detail["sets"],
            steps=detail["steps"],
        )
    ]
