"""P2-M7-R1 · A6 rotation issue locale 文案单测."""

from __future__ import annotations

from app.pipeline.diagnose import diagnose
from app.pipeline.rotation_issue_copy import (
    get_zh_cn_locale,
    render_rotation_issue_description,
    should_use_safe_rotation_summary,
)
from app.pipeline.rule_engine import LOCALES_DIR, load_locale
from tests.test_diagnose import _fake_phases, _ideal_features


def test_locale_has_rotation_a6_keys() -> None:
    locale = load_locale(LOCALES_DIR / "zh_CN.json")
    assert "issues.rotation_unreliable.title" in locale
    assert "issues.rotation_unreliable.summary" in locale
    for t in ("over_rotation", "under_rotation", "flat_shoulder", "steep_shoulder"):
        assert f"issues.{t}.summary_safe" in locale


def test_safe_summary_omits_absurd_shoulder_degrees() -> None:
    locale = get_zh_cn_locale()
    text = render_rotation_issue_description(
        "under_rotation", {"shoulder_rotation_top": 3.0}, locale
    )
    assert "3" not in text
    assert "°" not in text or "理想" in text
    assert should_use_safe_rotation_summary("under_rotation", {"shoulder_rotation_top": 3.0})


def test_numeric_summary_when_shoulder_in_band() -> None:
    locale = get_zh_cn_locale()
    text = render_rotation_issue_description(
        "under_rotation", {"shoulder_rotation_top": 60.0}, locale
    )
    assert "60" in text
    assert not should_use_safe_rotation_summary(
        "under_rotation", {"shoulder_rotation_top": 60.0}
    )


def test_safe_summary_for_absurd_x_factor() -> None:
    locale = get_zh_cn_locale()
    text = render_rotation_issue_description(
        "flat_shoulder", {"x_factor": 155.0}, locale
    )
    assert "155" not in text
    assert should_use_safe_rotation_summary("flat_shoulder", {"x_factor": 155.0})


def test_v1_diagnose_under_rotation_uses_safe_copy_at_borderline() -> None:
    feats = _ideal_features()
    feats["shoulder_rotation_top"] = 12.0
    feats["top_wrist_position"] = 0.05
    issues = diagnose(feats, _fake_phases(), camera_angle="face_on")
    under = [i for i in issues if i.type == "under_rotation"]
    assert len(under) == 1
    assert "12" not in under[0].description
    assert "偏小" in under[0].description or "理想" in under[0].description
