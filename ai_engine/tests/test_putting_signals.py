"""P2-M7-11 W20-A · 推杆诊断信号单测。"""

from __future__ import annotations

import math

import numpy as np

from app.pipeline.pose import (
    LANDMARK_LEFT_ELBOW,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_NOSE,
    LANDMARK_RIGHT_WRIST,
)
from app.pipeline.putting.diagnose import diagnose_putting
from app.pipeline.putting.phases import PuttingPhaseInfo, PuttingPhaseResult
from app.pipeline.putting.signals import (
    DECEL_SPEED_RATIO,
    PUTTER_LIFT_NORM,
    SETUP_AIM_OFFSET_DEG,
    SHORT_BACKSTROKE_RATIO,
    WRIST_HINGE_TRIGGER_DEG,
    extract_putting_diagnostic_signals,
)


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
        lead_wrist_idx=LANDMARK_LEFT_WRIST,
        lead_shoulder_idx=LANDMARK_LEFT_SHOULDER,
        handedness="right",
        fps=30.0,
    )


def _base_keypoints(n: int = 45) -> np.ndarray:
    kp = np.zeros((n, 33, 3), dtype=np.float32)
    kp[:, LANDMARK_NOSE, :2] = [0.5, 0.3]
    kp[:, LANDMARK_LEFT_SHOULDER, :2] = [0.45, 0.35]
    kp[:, LANDMARK_LEFT_ELBOW, :2] = [0.44, 0.42]
    for i in range(n):
        kp[i, LANDMARK_LEFT_WRIST, :2] = [0.43, 0.48 + i * 0.0005]
        kp[i, LANDMARK_RIGHT_WRIST, :2] = [0.47, 0.48 + i * 0.0005]
    return kp


def test_extract_signals_returns_finite_keys() -> None:
    sig = extract_putting_diagnostic_signals(_base_keypoints(), _phases())
    assert set(sig) == {
        "wrist_hinge_delta_deg",
        "backstroke_amp_ratio",
        "decel_speed_ratio",
        "setup_aim_offset_deg",
        "putter_lift_norm",
    }


def test_wrist_hinge_rule_triggers_from_signals() -> None:
    issues = diagnose_putting(
        {"pendulum_stability": 0, "head_stability": 0, "face_alignment": 0, "tempo_ratio": 2.2},
        _phases(),
        signals={"wrist_hinge_delta_deg": WRIST_HINGE_TRIGGER_DEG + 5},
    )
    assert any(i.type == "putting_wrist_hinge" for i in issues)


def test_short_backstroke_rule_triggers() -> None:
    issues = diagnose_putting(
        {"pendulum_stability": 0, "head_stability": 0, "face_alignment": 0, "tempo_ratio": 2.2},
        _phases(),
        signals={"backstroke_amp_ratio": SHORT_BACKSTROKE_RATIO - 0.1},
    )
    assert any(i.type == "putting_short_backstroke" for i in issues)


def test_decel_stroke_rule_triggers() -> None:
    issues = diagnose_putting(
        {"pendulum_stability": 0, "head_stability": 0, "face_alignment": 0, "tempo_ratio": 2.2},
        _phases(),
        signals={"decel_speed_ratio": DECEL_SPEED_RATIO - 0.2},
    )
    assert any(i.type == "putting_decel_stroke" for i in issues)


def test_aim_off_rule_triggers() -> None:
    issues = diagnose_putting(
        {"pendulum_stability": 0, "head_stability": 0, "face_alignment": 0, "tempo_ratio": 2.2},
        _phases(),
        signals={"setup_aim_offset_deg": SETUP_AIM_OFFSET_DEG + 4},
    )
    assert any(i.type == "putting_aim_off" for i in issues)


def test_lift_putter_rule_triggers() -> None:
    issues = diagnose_putting(
        {"pendulum_stability": 0, "head_stability": 0, "face_alignment": 0, "tempo_ratio": 2.2},
        _phases(),
        signals={"putter_lift_norm": PUTTER_LIFT_NORM + 0.01},
    )
    assert any(i.type == "putting_lift_putter" for i in issues)


def test_nan_signals_skip_signal_rules() -> None:
    nan_sig = {k: float("nan") for k in (
        "wrist_hinge_delta_deg",
        "backstroke_amp_ratio",
        "decel_speed_ratio",
        "setup_aim_offset_deg",
        "putter_lift_norm",
    )}
    issues = diagnose_putting(
        {"pendulum_stability": 0, "head_stability": 0, "face_alignment": 0, "tempo_ratio": 2.2},
        _phases(),
        signals=nan_sig,
    )
    signal_types = {
        "putting_wrist_hinge",
        "putting_short_backstroke",
        "putting_decel_stroke",
        "putting_aim_off",
        "putting_lift_putter",
    }
    assert not signal_types.intersection({i.type for i in issues})


def test_keypoints_path_computes_signals() -> None:
    kp = _base_keypoints()
    # follow 段主腕明显上抬
    kp[26:41, LANDMARK_LEFT_WRIST, 1] -= 0.02
    issues = diagnose_putting(
        {"pendulum_stability": 0, "head_stability": 0, "face_alignment": 0, "tempo_ratio": 2.2},
        _phases(),
        keypoints=kp,
        valid_mask=np.ones(len(kp), dtype=bool),
    )
    sig = extract_putting_diagnostic_signals(kp, _phases())
    assert math.isfinite(sig["putter_lift_norm"]) or not any(i.type == "putting_lift_putter" for i in issues)
