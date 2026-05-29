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
    """构造一套真正『无问题挥杆』特征：每条 rule 都落在安全区间。

    不能简单取各特征 ideal 区间中点——区间是『评分容差带』（配合 tolerance 给分），
    比 diagnose 各 rule 的『良好』阈值宽。例如 shoulder_rotation_top 区间 30-95、
    中点 62.5，会落进 under_rotation(<75) 的触发区；finish_height 区间 -0.20~0.15、
    中点 -0.025，会落进 chicken_wing(>-0.05) 的触发区。这里按 rule 的无问题条件取值。
    """
    feats = {f["name"]: (f["ideal_min"] + f["ideal_max"]) / 2 for f in FEATURES}
    feats.update(
        {
            "shoulder_rotation_top": 90.0,  # under(<75)/over(>105) 之间
            "x_factor": 40.0,  # steep(<25)/flat(>60)/over_the_top(<55) 安全
            "downswing_sequence": 4.0,  # sway_lead(<-2)/over_the_top(seq<0) 安全
            "wrist_release_timing": 0.65,  # casting(<0.40) 安全
            "spine_angle_impact_delta": 2.0,  # early_extension(>8)/loss_of_posture 安全
            "head_lateral_shift": 0.02,  # sway_slide(>0.12)/loss_of_posture 安全
            "top_wrist_position": 0.25,  # reverse_spine(<0) 安全
            "left_arm_straightness": 175.0,  # chicken_wing(arm<150) 安全
            "finish_height": -0.10,  # chicken_wing(finish_h>-0.05) 安全
            "finish_balance": 0.01,  # hanging_back(>0.04) 安全
            "knee_flexion_setup": 158.0,  # open_stance(>170) 安全
        }
    )
    return feats


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
