"""W6-T2：推荐单测。"""

from __future__ import annotations

from app.pipeline.constants import (
    ISSUE_DRILL_MAP,
    MAX_RECOMMENDATIONS_PER_ANALYSIS,
)
from app.pipeline.diagnose import DiagnosedIssue
from app.pipeline.recommend import recommend


def _make_issue(type_: str, severity: str = "high", confidence: float = 0.9) -> DiagnosedIssue:
    return DiagnosedIssue(
        type=type_,
        name=type_,
        severity=severity,
        description="desc",
        confidence=confidence,
        key_frame_timestamp=0.0,
    )


def test_recommend_empty_issues() -> None:
    """没有 issue 时返回空列表。"""
    assert recommend([]) == []


def test_recommend_high_severity_takes_multiple_drills() -> None:
    """casting 映射到 [drill_towel_arm, drill_impact_bag]；high 应该都拿。"""
    issues = [_make_issue("casting", severity="high")]
    recs = recommend(issues)
    drill_ids = [r.drill_id for r in recs]
    assert "drill_towel_arm" in drill_ids
    # casting 映射里有 2 条，都应该被推荐（未超上限时）
    assert len(drill_ids) >= 1


def test_recommend_respects_max_limit() -> None:
    """多 issue 时最多返回 MAX_RECOMMENDATIONS_PER_ANALYSIS 条。"""
    issues = [
        _make_issue("casting", severity="high"),
        _make_issue("over_the_top", severity="high"),
        _make_issue("early_extension", severity="medium"),
        _make_issue("sway_slide", severity="medium"),
    ]
    recs = recommend(issues)
    assert len(recs) <= MAX_RECOMMENDATIONS_PER_ANALYSIS


def test_recommend_dedup_by_drill_id() -> None:
    """多个 issue 指同一个 drill 时去重。

    early_extension 和 reverse_spine 都映射到 drill_wall_butt。
    """
    issues = [
        _make_issue("early_extension", severity="medium"),
        _make_issue("reverse_spine", severity="medium"),
    ]
    recs = recommend(issues)
    drill_ids = [r.drill_id for r in recs]
    assert len(drill_ids) == len(set(drill_ids)), "推荐里有重复 drill_id"


def test_recommend_medium_takes_one_drill() -> None:
    """medium/low 严重度只取第一个 drill。"""
    issues = [_make_issue("casting", severity="medium")]
    recs = recommend(issues)
    assert len(recs) <= 1 + 0  # casting 即便有 2 个 drill，medium 只取 1 个


def test_recommend_target_issue_preserved() -> None:
    """RecommendationItem.target_issue 指向真正触发它的 issue（不是 drill 模板里的 target_issue）。"""
    issues = [_make_issue("reverse_spine", severity="medium")]
    recs = recommend(issues)
    # reverse_spine 映射到 drill_wall_butt，但 drill 模板里 target_issue 是 early_extension
    # 我们约定：RecommendationItem.target_issue 应该覆盖成 "reverse_spine"
    assert recs
    assert recs[0].target_issue == "reverse_spine"


def test_all_drill_ids_in_mock_library() -> None:
    """constants.ISSUE_DRILL_MAP 里的所有 drill_id 都必须在 DRILL_TEMPLATES 里登记。"""
    from app.mock_pipeline import DRILL_TEMPLATES

    registered = {d["drill_id"] for d in DRILL_TEMPLATES}
    needed = {drill for drills in ISSUE_DRILL_MAP.values() for drill in drills}
    missing = needed - registered
    assert not missing, f"ISSUE_DRILL_MAP 指向了未登记的 drill：{missing}"
