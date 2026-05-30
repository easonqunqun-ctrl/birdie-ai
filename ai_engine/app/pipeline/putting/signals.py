"""P2-M7-11 W20-A · 推杆诊断辅助信号（手腕角 / 速度时序）。

kickoff §3.5 剩余 5 条诊断依赖的时序量；M7-09 杆追踪到位前用 pose 代理。
任一信号算不出时返回 ``nan``，对应 rule 跳过（不硬凑）。
"""

from __future__ import annotations

import logging
import math

import numpy as np

from app.pipeline.pose import (
    LANDMARK_LEFT_ELBOW,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_ELBOW,
    LANDMARK_RIGHT_WRIST,
)
from app.pipeline.putting.phases import PuttingPhaseResult, _wrist_speed

log = logging.getLogger("ai_engine.putting.signals")

_EPS = 1e-8
_NAN = float("nan")

# kickoff §3.5 草案阈值（v0.1 占位，待 ECS 标定）
WRIST_HINGE_TRIGGER_DEG = 8.0
SHORT_BACKSTROKE_RATIO = 0.5
DECEL_SPEED_RATIO = 0.8
SETUP_AIM_OFFSET_DEG = 5.0
PUTTER_LIFT_NORM = 0.012


def _clip(frame: int, n: int) -> int:
    return max(0, min(frame, n - 1))


def _angle_at_joint(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """顶点 b 处夹角（度）。"""
    v1 = a - b
    v2 = c - b
    denom = float(np.linalg.norm(v1) * np.linalg.norm(v2)) + _EPS
    cos = float(np.dot(v1, v2)) / denom
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def _angle_2d_deg(v1: np.ndarray, v2: np.ndarray) -> float:
    denom = float(np.linalg.norm(v1) * np.linalg.norm(v2)) + _EPS
    cos = float(np.dot(v1, v2)) / denom
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def _face_offset_deg(keypoints: np.ndarray, frame: int, lead: int, stroke_vec: np.ndarray) -> float:
    """握把线偏离「与击球方向垂直（方正）」的角度。"""
    if float(np.linalg.norm(stroke_vec)) < 1e-4:
        return _NAN
    hand_line = (
        keypoints[frame, LANDMARK_RIGHT_WRIST, :2]
        - keypoints[frame, LANDMARK_LEFT_WRIST, :2]
    )
    if float(np.linalg.norm(hand_line)) < 1e-4:
        return _NAN
    angle = _angle_2d_deg(hand_line, stroke_vec)
    return abs(90.0 - angle)


def _mean_speed(speeds: np.ndarray, start: int, end: int) -> float:
    if end <= start:
        return _NAN
    seg = speeds[start : end + 1]
    if len(seg) == 0:
        return _NAN
    return float(np.mean(seg))


def extract_putting_diagnostic_signals(
    keypoints: np.ndarray,
    phases: PuttingPhaseResult,
    valid_mask: np.ndarray | None = None,
) -> dict[str, float]:
    """从 pose 时序提取推杆诊断辅助信号。"""
    n = len(keypoints)
    if n == 0:
        return _empty_signals()

    mask = valid_mask if valid_mask is not None else np.ones(n, dtype=bool)
    lead = phases.lead_wrist_idx
    elbow = LANDMARK_LEFT_ELBOW if lead == LANDMARK_LEFT_WRIST else LANDMARK_RIGHT_ELBOW
    shoulder = phases.lead_shoulder_idx

    bs = phases.phases["backstroke"]
    setup = phases.phases["setup"]
    follow = phases.phases["follow"]
    impact = phases.impact_frame

    bs_start = _clip(bs.start_frame, n)
    bs_end = _clip(bs.end_frame, n)
    setup_frame = _clip(setup.key_frame, n)
    follow_end = _clip(follow.end_frame, n)

    stroke_vec = keypoints[impact, lead, :2] - keypoints[bs_start, lead, :2]

    # --- wrist hinge: 挥动窗口内肩-肘-腕角变化 ---
    hinge_delta = _NAN
    angles: list[float] = []
    for i in range(phases.swing_start, min(phases.swing_end, n - 1) + 1):
        if not mask[i]:
            continue
        a = keypoints[i, shoulder, :2]
        b = keypoints[i, elbow, :2]
        c = keypoints[i, lead, :2]
        if float(np.linalg.norm(a - b)) < 1e-4 or float(np.linalg.norm(c - b)) < 1e-4:
            continue
        angles.append(_angle_at_joint(a, b, c))
    if len(angles) >= 2:
        hinge_delta = max(angles) - min(angles)

    # --- short backstroke: 回摆位移 vs 前推位移 ---
    back_disp = float(np.linalg.norm(keypoints[bs_end, lead, :2] - keypoints[bs_start, lead, :2]))
    fwd_disp = float(np.linalg.norm(keypoints[impact, lead, :2] - keypoints[bs_end, lead, :2]))
    backstroke_amp_ratio = back_disp / fwd_disp if fwd_disp > 1e-4 else _NAN

    # --- decel: follow 均速 vs backstroke 均速 ---
    speeds = _wrist_speed(keypoints, mask, lead)
    back_mean = _mean_speed(speeds, bs_start, bs_end)
    follow_mean = _mean_speed(speeds, min(impact + 1, n - 1), follow_end)
    decel_ratio = follow_mean / back_mean if back_mean and math.isfinite(back_mean) and back_mean > _EPS else _NAN

    # --- setup aim: setup 帧杆面 vs 最终击球方向 ---
    setup_aim_offset = _face_offset_deg(keypoints, setup_frame, lead, stroke_vec)

    # --- putter lift: follow 段主腕 y 上抬（MediaPipe y 向下为正 → 上抬为 y 减小）---
    follow_slice = keypoints[impact : follow_end + 1, lead, 1]
    if len(follow_slice) >= 2:
        putter_lift = float(keypoints[impact, lead, 1] - float(np.min(follow_slice)))
    else:
        putter_lift = _NAN

    out = {
        "wrist_hinge_delta_deg": hinge_delta,
        "backstroke_amp_ratio": backstroke_amp_ratio,
        "decel_speed_ratio": decel_ratio,
        "setup_aim_offset_deg": setup_aim_offset,
        "putter_lift_norm": putter_lift,
    }
    for k, v in out.items():
        if not math.isfinite(v):
            out[k] = _NAN
    return out


def _empty_signals() -> dict[str, float]:
    return {
        "wrist_hinge_delta_deg": _NAN,
        "backstroke_amp_ratio": _NAN,
        "decel_speed_ratio": _NAN,
        "setup_aim_offset_deg": _NAN,
        "putter_lift_norm": _NAN,
    }
