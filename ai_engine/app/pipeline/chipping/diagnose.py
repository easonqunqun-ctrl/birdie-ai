"""P2-M7-12 · 切杆问题诊断（6 条 rule，基于 pose proxy）。"""

from __future__ import annotations

import logging

import numpy as np

from app.pipeline.diagnose import DiagnosedIssue
from app.pipeline.pose import LANDMARK_LEFT_ANKLE, LANDMARK_LEFT_WRIST, LANDMARK_RIGHT_ANKLE
from app.pipeline.chipping.phases import ChippingPhaseResult

log = logging.getLogger("ai_engine.chipping.diagnose")

MIN_DISPLAY_CONFIDENCE = 0.6
MAX_ISSUES = 5

CHIPPING_ISSUE_NAMES: dict[str, str] = {
    "chipping_over_swing": "上杆过大",
    "chipping_decel": "减速击球",
    "chipping_scoop": "挑球/scoop",
    "chipping_chunked": "打厚",
    "chipping_thin": "打薄",
    "chipping_alignment_off": "站位对准偏",
}


def _severity(dev: float, low: float = 0.3, high: float = 0.8) -> str:
    if dev >= high:
        return "high"
    if dev >= low:
        return "medium"
    return "low"


def _frame_time(frame: int, fps: float) -> float | None:
    return round(frame / fps, 2) if fps > 0 else None


def _mean_wrist_speed(
    keypoints: np.ndarray, start: int, end: int, wrist_idx: int
) -> float:
    if end <= start:
        return 0.0
    seg = keypoints[start : end + 1, wrist_idx, :2]
    speeds = np.linalg.norm(np.diff(seg, axis=0), axis=1)
    return float(np.mean(speeds)) if len(speeds) else 0.0


def _rule_over_swing(feat: dict[str, float], phases: ChippingPhaseResult) -> DiagnosedIssue | None:
    val = feat["half_swing_amplitude"]
    if val <= 0.7:
        return None
    dev = (val - 0.7) / 0.3
    return DiagnosedIssue(
        type="chipping_over_swing",
        name=CHIPPING_ISSUE_NAMES["chipping_over_swing"],
        severity=_severity(dev),
        description=f"半挥幅度 {val:.2f} 偏大（理想 0.3-0.6），切杆不需要全挥幅度。",
        confidence=min(1.0, 0.6 + dev * 0.3),
        key_frame_timestamp=_frame_time(phases.top_frame, phases.fps),
        metrics={"half_swing_amplitude": val},
    )


def _rule_decel(
    feat: dict[str, float], phases: ChippingPhaseResult, keypoints: np.ndarray
) -> DiagnosedIssue | None:
    bs = phases.phases["backswing"]
    fo = phases.phases["follow"]
    lead = phases.lead_wrist_idx
    bs_speed = _mean_wrist_speed(keypoints, bs.start_frame, bs.end_frame, lead)
    fo_speed = _mean_wrist_speed(keypoints, fo.start_frame, fo.end_frame, lead)
    if bs_speed <= 0 or fo_speed >= bs_speed * 0.7:
        return None
    dev = (0.7 - fo_speed / bs_speed) / 0.3
    return DiagnosedIssue(
        type="chipping_decel",
        name=CHIPPING_ISSUE_NAMES["chipping_decel"],
        severity=_severity(dev),
        description="收杆段腕速明显低于上杆，存在减速通过球的风险。",
        confidence=min(1.0, 0.6 + dev * 0.3),
        key_frame_timestamp=_frame_time(phases.impact_frame, phases.fps),
        metrics={"backswing_speed": bs_speed, "follow_speed": fo_speed},
    )


def _rule_scoop(
    feat: dict[str, float], phases: ChippingPhaseResult, keypoints: np.ndarray
) -> DiagnosedIssue | None:
    pre = max(phases.swing_start, phases.impact_frame - 3)
    lead = phases.lead_wrist_idx
    lead_ankle = LANDMARK_LEFT_ANKLE if lead == LANDMARK_LEFT_WRIST else LANDMARK_RIGHT_ANKLE
    wrist_x = keypoints[pre, lead, 0]
    foot_x = keypoints[pre, lead_ankle, 0]
    ahead = wrist_x - foot_x
    if ahead <= 0.02:
        return None
    dev = ahead / 0.05
    return DiagnosedIssue(
        type="chipping_scoop",
        name=CHIPPING_ISSUE_NAMES["chipping_scoop"],
        severity=_severity(dev),
        description="击球前手位明显领先脚位，容易 scoop 挑球打高。",
        confidence=min(1.0, 0.55 + dev * 0.3),
        key_frame_timestamp=_frame_time(pre, phases.fps),
        metrics={"wrist_ahead_of_foot": ahead},
    )


def _rule_chunked(
    feat: dict[str, float], phases: ChippingPhaseResult, keypoints: np.ndarray
) -> DiagnosedIssue | None:
    lead = phases.lead_wrist_idx
    pre = max(phases.swing_start, phases.impact_frame - 2)
    drop = keypoints[pre, lead, 1] - keypoints[phases.impact_frame, lead, 1]
    if drop <= 0.04:
        return None
    dev = drop / 0.06
    return DiagnosedIssue(
        type="chipping_chunked",
        name=CHIPPING_ISSUE_NAMES["chipping_chunked"],
        severity=_severity(dev),
        description="击球前手腕明显下沉，容易打厚（chunk）。",
        confidence=min(1.0, 0.55 + dev * 0.3),
        key_frame_timestamp=_frame_time(pre, phases.fps),
        metrics={"wrist_drop_before_impact": drop},
    )


def _rule_thin(
    feat: dict[str, float], phases: ChippingPhaseResult, keypoints: np.ndarray
) -> DiagnosedIssue | None:
    setup = phases.phases["setup"].key_frame
    lead = phases.lead_wrist_idx
    rise = keypoints[phases.impact_frame, lead, 1] - keypoints[setup, lead, 1]
    if rise <= -0.03:
        return None
    dev = rise / 0.05
    return DiagnosedIssue(
        type="chipping_thin",
        name=CHIPPING_ISSUE_NAMES["chipping_thin"],
        severity=_severity(dev),
        description="击球时手位偏高，杆头容易从球下方通过（打薄）。",
        confidence=min(1.0, 0.55 + dev * 0.3),
        key_frame_timestamp=_frame_time(phases.impact_frame, phases.fps),
        metrics={"wrist_rise_at_impact": rise},
    )


def _rule_alignment_off(
    feat: dict[str, float], phases: ChippingPhaseResult, keypoints: np.ndarray
) -> DiagnosedIssue | None:
    setup = phases.phases["setup"].key_frame
    foot_vec = (
        keypoints[setup, LANDMARK_RIGHT_ANKLE, :2]
        - keypoints[setup, LANDMARK_LEFT_ANKLE, :2]
    )
    hand_vec = (
        keypoints[setup, 16, :2] - keypoints[setup, 15, :2]
    )
    if float(np.linalg.norm(foot_vec)) < 1e-4 or float(np.linalg.norm(hand_vec)) < 1e-4:
        return None
    cos = float(np.dot(foot_vec, hand_vec)) / (
        float(np.linalg.norm(foot_vec) * np.linalg.norm(hand_vec)) + 1e-8
    )
    angle = float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))
    if angle <= 10.0:
        return None
    dev = (angle - 10.0) / 15.0
    return DiagnosedIssue(
        type="chipping_alignment_off",
        name=CHIPPING_ISSUE_NAMES["chipping_alignment_off"],
        severity=_severity(dev),
        description=f"准备位脚线与握把线夹角 {angle:.0f}° 偏大，站位对准可能有问题。",
        confidence=min(0.85, 0.55 + dev * 0.3),
        key_frame_timestamp=_frame_time(setup, phases.fps),
        metrics={"foot_hand_angle_deg": angle},
    )


def diagnose_chipping(
    features: dict[str, float],
    phases: ChippingPhaseResult,
    keypoints: np.ndarray,
    *,
    min_confidence: float = MIN_DISPLAY_CONFIDENCE,
    max_issues: int = MAX_ISSUES,
) -> list[DiagnosedIssue]:
    rules = [
        lambda: _rule_over_swing(features, phases),
        lambda: _rule_decel(features, phases, keypoints),
        lambda: _rule_scoop(features, phases, keypoints),
        lambda: _rule_chunked(features, phases, keypoints),
        lambda: _rule_thin(features, phases, keypoints),
        lambda: _rule_alignment_off(features, phases, keypoints),
    ]
    issues: list[DiagnosedIssue] = []
    for rule in rules:
        try:
            res = rule()
        except Exception as exc:  # pragma: no cover
            log.warning("chipping_rule_error", extra={"error": str(exc)})
            continue
        if res and res.confidence >= min_confidence:
            issues.append(res)
    order = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda x: (order[x.severity], -x.confidence))
    return issues[:max_issues]
