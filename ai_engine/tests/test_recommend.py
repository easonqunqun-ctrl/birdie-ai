"""训练建议兜底单测。"""

from __future__ import annotations

from app.pipeline.recommend import recommend_with_phase_fallback


def test_phase_fallback_when_no_issues_and_low_score() -> None:
    recs = recommend_with_phase_fallback(
        [],
        phase_scores={
            "setup": 55,
            "backswing": 48,
            "top": 50,
            "downswing": 42,
            "impact": 58,
            "follow_through": 52,
        },
        overall_score=50,
        weakest_phase="downswing",
    )
    assert len(recs) == 1
    assert recs[0].drill_id == "drill_half_swing"
    assert "下杆转换" in recs[0].description


def test_no_fallback_when_issues_present() -> None:
    from app.pipeline.diagnose import DiagnosedIssue

    issues = [
        DiagnosedIssue(
            type="casting",
            name="抛杆",
            severity="high",
            description="x",
            confidence=0.9,
        )
    ]
    recs = recommend_with_phase_fallback(
        issues,
        phase_scores={"downswing": 40},
        overall_score=50,
        weakest_phase="downswing",
    )
    assert len(recs) >= 1
    assert recs[0].target_issue == "casting"


def test_no_fallback_when_score_not_low() -> None:
    recs = recommend_with_phase_fallback(
        [],
        phase_scores={"downswing": 72, "impact": 75},
        overall_score=74,
        weakest_phase="downswing",
    )
    assert recs == []
