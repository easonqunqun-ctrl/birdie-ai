"""P2-M7-12 · 切杆 3 个专属特征提取。

kickoff §3.2：
- ``half_swing_amplitude``：上杆顶点 lead 腕-同侧耳距离 / 准备位肩-腕距离
- ``face_open_angle``：击球点握把线相对挥动方向的「开角」（理想 5-15°）
- ``contact_point_quality``：击球帧手-脚-球位 proxy 几何分 0-100
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from app.pipeline.pose import (
    LANDMARK_LEFT_ANKLE,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_ANKLE,
    LANDMARK_RIGHT_WRIST,
)
from app.pipeline.chipping.constants import CHIPPING_FEATURES, chipping_feature_meta

if TYPE_CHECKING:
    from app.pipeline.chipping.phases import ChippingPhaseResult

log = logging.getLogger("ai_engine.chipping.features")

# MediaPipe Pose 耳索引（未在 pose.py 导出，局部常量）
_LANDMARK_LEFT_EAR = 7
_LANDMARK_RIGHT_EAR = 8
_EPS = 1e-8


def _clip_idx(n: int, idx: int) -> int:
    return max(0, min(idx, n - 1))


def _angle_2d_deg(v1: np.ndarray, v2: np.ndarray) -> float:
    denom = float(np.linalg.norm(v1) * np.linalg.norm(v2)) + _EPS
    cos = float(np.dot(v1, v2)) / denom
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def _lead_ear_idx(phases: ChippingPhaseResult) -> int:
    return _LANDMARK_LEFT_EAR if phases.lead_wrist_idx == LANDMARK_LEFT_WRIST else _LANDMARK_RIGHT_EAR


def _lead_ankle_idx(phases: ChippingPhaseResult) -> int:
    return LANDMARK_LEFT_ANKLE if phases.lead_wrist_idx == LANDMARK_LEFT_WRIST else LANDMARK_RIGHT_ANKLE


def feat_half_swing_amplitude(keypoints: np.ndarray, phases: ChippingPhaseResult) -> float:
    """半挥幅度比：顶点上腕-耳 / setup 肩-腕。"""
    top = _clip_idx(len(keypoints), phases.top_frame)
    setup = _clip_idx(len(keypoints), phases.phases["setup"].key_frame)
    lead = phases.lead_wrist_idx
    ear = _lead_ear_idx(phases)
    shoulder = phases.lead_shoulder_idx

    ref = float(np.linalg.norm(keypoints[setup, lead, :2] - keypoints[setup, shoulder, :2]))
    if ref < 1e-4:
        raise ValueError("setup 肩-腕距离过小")
    amp = float(np.linalg.norm(keypoints[top, lead, :2] - keypoints[top, ear, :2]))
    return amp / ref


def feat_face_open_angle(keypoints: np.ndarray, phases: ChippingPhaseResult) -> float:
    """击球点杆面开角（度）：握把线相对挥动方向，90°=方正，<90°=开。"""
    impact = _clip_idx(len(keypoints), phases.impact_frame)
    bs_start = _clip_idx(len(keypoints), phases.phases["backswing"].start_frame)
    lead = phases.lead_wrist_idx

    stroke = keypoints[impact, lead, :2] - keypoints[bs_start, lead, :2]
    if float(np.linalg.norm(stroke)) < 1e-4:
        raise ValueError("挥动方向过小")

    hand_line = (
        keypoints[impact, LANDMARK_RIGHT_WRIST, :2]
        - keypoints[impact, LANDMARK_LEFT_WRIST, :2]
    )
    if float(np.linalg.norm(hand_line)) < 1e-4:
        raise ValueError("双腕连线过短")

    angle = _angle_2d_deg(hand_line, stroke)
    # 开角：偏离方正 90° 的量；切杆通常略开 → 返回 |90-angle| 作为开角 proxy
    return abs(90.0 - angle)


def feat_contact_point_quality(keypoints: np.ndarray, phases: ChippingPhaseResult) -> float:
    """触球质量 0-100：手略在脚前、重心在 lead 脚、击球高度合理。"""
    impact = _clip_idx(len(keypoints), phases.impact_frame)
    setup = _clip_idx(len(keypoints), phases.phases["setup"].key_frame)
    lead = phases.lead_wrist_idx
    lead_ankle = _lead_ankle_idx(phases)
    trail_ankle = LANDMARK_RIGHT_ANKLE if lead_ankle == LANDMARK_LEFT_ANKLE else LANDMARK_LEFT_ANKLE

    foot_mid_x = (
        keypoints[impact, lead_ankle, 0] + keypoints[impact, trail_ankle, 0]
    ) / 2.0
    wrist_x = keypoints[impact, lead, 0]
    # 手在脚前（朝向目标侧）加分；face_on 下 x 增大为前
    ahead = (wrist_x - foot_mid_x) * 100.0  # 归一化差 ×100 作 proxy
    ahead_score = float(np.clip(50.0 + ahead * 200.0, 0.0, 50.0))

    setup_wrist_y = keypoints[setup, lead, 1]
    impact_wrist_y = keypoints[impact, lead, 1]
    height_delta = setup_wrist_y - impact_wrist_y  # 击球略低为正
    height_score = float(np.clip(30.0 + height_delta * 300.0, 0.0, 30.0))

    # 双脚宽度稳定 proxy
    foot_width = abs(
        keypoints[impact, lead_ankle, 0] - keypoints[impact, trail_ankle, 0]
    )
    width_score = float(np.clip(20.0 - abs(foot_width - 0.15) * 100.0, 0.0, 20.0))

    return min(100.0, ahead_score + height_score + width_score)


_FEATURE_FUNCS = {
    "half_swing_amplitude": feat_half_swing_amplitude,
    "face_open_angle": feat_face_open_angle,
    "contact_point_quality": feat_contact_point_quality,
}

assert set(_FEATURE_FUNCS) == {f["name"] for f in CHIPPING_FEATURES}


def extract_chipping_features(
    keypoints: np.ndarray, phases: ChippingPhaseResult
) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, fn in _FEATURE_FUNCS.items():
        try:
            value = float(fn(keypoints, phases))
            if not np.isfinite(value):
                raise ValueError("非有限值")
            out[name] = value
        except Exception as exc:  # noqa: BLE001
            meta = chipping_feature_meta(name)
            fallback = (meta["ideal_min"] + meta["ideal_max"]) / 2.0
            log.warning(
                "chipping_feature_fallback",
                extra={"feature": name, "error": str(exc), "fallback": fallback},
            )
            out[name] = fallback
    return out
