"""阶段亮点话术单测。"""

from __future__ import annotations

from app.pipeline.scoring_narrative import build_phase_highlights


def test_build_phase_highlights_picks_top_phases() -> None:
    lines = build_phase_highlights(
        {
            "setup": 45,
            "backswing": 50,
            "top": 42,
            "downswing": 83,
            "impact": 87,
            "follow_through": 65,
        }
    )
    assert len(lines) == 2
    assert "击球触球" in lines[0]
    assert "下杆转换" in lines[1]


def test_beginner_high_setup_gets_encouragement() -> None:
    lines = build_phase_highlights({"setup": 82, "backswing": 40, "impact": 55})
    assert len(lines) == 1
    assert "站位准备" in lines[0]


def test_encouragement_tier_at_70() -> None:
    lines = build_phase_highlights({"impact": 72, "downswing": 65, "setup": 40})
    assert any("击球触球" in ln and "较稳" in ln for ln in lines)


def test_angle_limited_preface() -> None:
    lines = build_phase_highlights(
        {"impact": 87, "downswing": 83},
        quality_warnings=["angle_limited_scoring"],
    )
    assert lines[0].startswith("当前机位下")
    assert any("击球触球" in ln for ln in lines)
