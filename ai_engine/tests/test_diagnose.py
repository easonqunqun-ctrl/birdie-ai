"""W6-T2：诊断单测。"""

from __future__ import annotations

from app.pipeline.constants import FEATURES
from app.pipeline.diagnose import MIN_DISPLAY_CONFIDENCE, DiagnosedIssue, diagnose
from app.pipeline.phases import PhaseInfo, PhaseSegmentResult
from app.pipeline.pose import LANDMARK_LEFT_SHOULDER, LANDMARK_LEFT_WRIST


def _fake_phases(fps: float = 30.0) -> PhaseSegmentResult:
    """造一个最小化的 PhaseSegmentResult，用于 rule 测试。"""
    return PhaseSegmentResult(
        phases={
            "setup": PhaseInfo(0, 5, 5),
            "backswing": PhaseInfo(5, 14, 10),
            "top": PhaseInfo(15, 15, 15),
            "downswing": PhaseInfo(16, 20, 18),
            "impact": PhaseInfo(21, 21, 21),
            "follow_through": PhaseInfo(22, 29, 25),
        },
        swing_start=5,
        swing_end=25,
        top_frame=15,
        impact_frame=21,
        handedness="right",
        lead_wrist_idx=LANDMARK_LEFT_WRIST,
        lead_shoulder_idx=LANDMARK_LEFT_SHOULDER,
        fps=fps,
    )


def _ideal_features() -> dict[str, float]:
    """所有特征都在 ideal 中点：应该诊断出 0 条 issue（无问题挥杆）。"""
    return {f["name"]: (f["ideal_min"] + f["ideal_max"]) / 2 for f in FEATURES}


def test_diagnose_ideal_swing_no_issues() -> None:
    """理想挥杆不应触发任何规则。"""
    feats = _ideal_features()
    phases = _fake_phases()
    issues = diagnose(feats, phases)
    assert issues == []


def test_diagnose_casting_triggered() -> None:
    feats = _ideal_features()
    feats["wrist_release_timing"] = 0.20  # < 0.40 触发 casting
    issues = diagnose(feats, _fake_phases())
    casting = [i for i in issues if i.type == "casting"]
    assert casting, "casting 应该被触发"
    assert casting[0].severity == "high"
    assert casting[0].confidence >= MIN_DISPLAY_CONFIDENCE


def test_diagnose_early_extension_triggered() -> None:
    feats = _ideal_features()
    feats["spine_angle_impact_delta"] = 12.0  # > 8 触发
    issues = diagnose(feats, _fake_phases())
    types = {i.type for i in issues}
    assert "early_extension" in types


def test_diagnose_sway_slide_triggered() -> None:
    feats = _ideal_features()
    feats["head_lateral_shift"] = 0.18  # > 0.12 触发
    issues = diagnose(feats, _fake_phases())
    types = {i.type for i in issues}
    assert "sway_slide" in types


def test_diagnose_under_rotation_triggered() -> None:
    feats = _ideal_features()
    feats["shoulder_rotation_top"] = 60.0  # < 75 触发
    issues = diagnose(feats, _fake_phases())
    types = {i.type for i in issues}
    assert "under_rotation" in types


def test_diagnose_over_rotation_triggered() -> None:
    feats = _ideal_features()
    feats["shoulder_rotation_top"] = 115.0  # > 105 触发
    issues = diagnose(feats, _fake_phases())
    types = {i.type for i in issues}
    assert "over_rotation" in types


def test_diagnose_reverse_spine_triggered() -> None:
    feats = _ideal_features()
    feats["top_wrist_position"] = -0.15
    issues = diagnose(feats, _fake_phases())
    types = {i.type for i in issues}
    assert "reverse_spine" in types


def test_diagnose_sort_by_severity() -> None:
    """多 issue 时按严重度排序。"""
    feats = _ideal_features()
    feats["wrist_release_timing"] = 0.10  # high casting
    feats["top_wrist_position"] = -0.02  # 轻微 reverse_spine
    issues = diagnose(feats, _fake_phases())
    severities = [i.severity for i in issues]
    # high 应该在前面
    assert severities.index("high") == 0 if "high" in severities else True


def test_diagnose_returns_list_of_diagnosed_issue() -> None:
    feats = _ideal_features()
    feats["wrist_release_timing"] = 0.05
    issues = diagnose(feats, _fake_phases())
    for i in issues:
        assert isinstance(i, DiagnosedIssue)
        assert i.name
        assert i.description
        assert 0 <= i.confidence <= 1
        assert i.severity in {"high", "medium", "low"}
