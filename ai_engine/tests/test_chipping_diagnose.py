"""P2-M7-12 · 切杆诊断单测。"""

from __future__ import annotations

from app.pipeline.chipping.diagnose import diagnose_chipping
from app.pipeline.chipping.phases import ChippingPhaseInfo, ChippingPhaseResult


def _phases() -> ChippingPhaseResult:
    return ChippingPhaseResult(
        phases={
            "setup": ChippingPhaseInfo(0, 5, 5),
            "backswing": ChippingPhaseInfo(6, 18, 15),
            "impact": ChippingPhaseInfo(25, 25, 25),
            "follow": ChippingPhaseInfo(26, 40, 33),
        },
        impact_frame=25,
        top_frame=15,
        swing_start=6,
        swing_end=34,
        lead_wrist_idx=15,
        lead_shoulder_idx=11,
        handedness="right",
        fps=30.0,
    )


def test_over_swing_triggers() -> None:
    import numpy as np

    feats = {
        "half_swing_amplitude": 0.9,
        "face_open_angle": 10.0,
        "contact_point_quality": 85.0,
    }
    kp = np.zeros((50, 33, 3), dtype=np.float32)
    issues = diagnose_chipping(feats, _phases(), kp)
    assert any(i.type == "chipping_over_swing" for i in issues)


def test_clean_stroke_few_issues() -> None:
    import numpy as np

    feats = {
        "half_swing_amplitude": 0.45,
        "face_open_angle": 10.0,
        "contact_point_quality": 90.0,
    }
    kp = np.zeros((50, 33, 3), dtype=np.float32)
    issues = diagnose_chipping(feats, _phases(), kp)
    assert not any(i.type == "chipping_over_swing" for i in issues)
