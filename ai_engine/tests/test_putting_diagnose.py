"""P2-M7-11 W25 · 推杆诊断单测。"""

from __future__ import annotations

from app.pipeline.putting.constants import putting_feature_meta
from app.pipeline.putting.diagnose import diagnose_putting
from app.pipeline.putting.phases import PuttingPhaseInfo, PuttingPhaseResult


def _phases() -> PuttingPhaseResult:
    return PuttingPhaseResult(
        phases={
            "setup": PuttingPhaseInfo(0, 5, 5),
            "backstroke": PuttingPhaseInfo(6, 18, 12),
            "impact": PuttingPhaseInfo(25, 25, 25),
            "follow": PuttingPhaseInfo(26, 40, 33),
        },
        impact_frame=25,
        swing_start=6,
        swing_end=34,
        lead_wrist_idx=15,
        lead_shoulder_idx=11,
        handedness="right",
        fps=30.0,
    )


_GOOD = {
    "pendulum_stability": 0.0,
    "head_stability": 0.0,
    "face_alignment": 0.0,
    "tempo_ratio": 2.25,
}


def test_clean_stroke_no_issues() -> None:
    assert diagnose_putting(_GOOD, _phases()) == []


def test_face_open_triggers() -> None:
    feat = {**_GOOD, "face_alignment": 20.0}
    issues = diagnose_putting(feat, _phases())
    assert any(i.type == "putting_face_open" for i in issues)


def test_head_moved_triggers() -> None:
    ideal_max = putting_feature_meta("head_stability")["ideal_max"]
    feat = {**_GOOD, "head_stability": ideal_max * 6}
    issues = diagnose_putting(feat, _phases())
    assert any(i.type == "putting_head_moved" for i in issues)


def test_unstable_pendulum_triggers() -> None:
    ideal_max = putting_feature_meta("pendulum_stability")["ideal_max"]
    feat = {**_GOOD, "pendulum_stability": ideal_max * 6}
    issues = diagnose_putting(feat, _phases())
    assert any(i.type == "putting_unstable_pendulum" for i in issues)


def test_rushed_tempo_triggers() -> None:
    feat = {**_GOOD, "tempo_ratio": 1.0}
    issues = diagnose_putting(feat, _phases())
    assert any(i.type == "putting_rushed_tempo" for i in issues)


def test_slow_tempo_triggers() -> None:
    feat = {**_GOOD, "tempo_ratio": 5.5}
    issues = diagnose_putting(feat, _phases())
    assert any(i.type == "putting_slow_tempo" for i in issues)


def test_rushed_and_slow_mutually_exclusive() -> None:
    """同一 tempo 值不可能同时触发急/慢。"""
    for tempo in (1.0, 2.25, 5.5):
        types = {i.type for i in diagnose_putting({**_GOOD, "tempo_ratio": tempo}, _phases())}
        assert not ("putting_rushed_tempo" in types and "putting_slow_tempo" in types)


def test_issues_have_key_frame_and_sorted_by_severity() -> None:
    feat = {
        "pendulum_stability": putting_feature_meta("pendulum_stability")["ideal_max"] * 6,
        "head_stability": putting_feature_meta("head_stability")["ideal_max"] * 6,
        "face_alignment": 30.0,
        "tempo_ratio": 1.0,
    }
    issues = diagnose_putting(feat, _phases())
    assert len(issues) >= 3
    order = {"high": 0, "medium": 1, "low": 2}
    sev = [order[i.severity] for i in issues]
    assert sev == sorted(sev)
    for i in issues:
        assert i.key_frame_timestamp is not None
