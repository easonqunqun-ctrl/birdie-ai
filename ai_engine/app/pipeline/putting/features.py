"""P2-M7-11 · 推杆 4 个专属特征提取（W22）。

kickoff §3.2：
- ``pendulum_stability``：双肩中点 y 在整段挥动的方差（钟摆是否平稳）
- ``head_stability``：鼻关键点 2D 位移方差（推杆要求头部极稳）
- ``face_alignment``：击球点处「握把线」偏离「与击球方向方正」的角度
- ``tempo_ratio``：backstroke 时长 / forward stroke 时长

设计约束（与 full_swing ``features.py`` 同款）
--------------------------------------------
- **绝不崩溃**：任意特征算不出来时退化为该特征 ideal 中点，避免下游假警报。
- 坐标统一 MediaPipe 归一化 ``[0,1]``，y 向下增长。
- ``face_alignment`` 在 M7-09 杆/球追踪到位前，用「双腕连线」近似推杆面朝向（v0.1 代理）。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from app.pipeline.pose import (
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_NOSE,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
)
from app.pipeline.putting.constants import PUTTING_FEATURES, putting_feature_meta

if TYPE_CHECKING:
    from app.pipeline.putting.phases import PuttingPhaseResult

log = logging.getLogger("ai_engine.putting.features")

_EPS = 1e-8


# ==================== 几何工具 ====================


def _clip_idx(keypoints: np.ndarray, frame_idx: int) -> int:
    return max(0, min(frame_idx, len(keypoints) - 1))


def _angle_2d_deg(v1: np.ndarray, v2: np.ndarray) -> float:
    """两个 2D 向量夹角，度数 [0, 180]。"""
    denom = float(np.linalg.norm(v1) * np.linalg.norm(v2)) + _EPS
    cos = float(np.dot(v1, v2)) / denom
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def _swing_window(phases: PuttingPhaseResult, n_frames: int) -> tuple[int, int]:
    """夹取 [swing_start, swing_end] 到合法帧范围，返回闭区间端点。"""
    s = _clip_idx_int(phases.swing_start, n_frames)
    e = _clip_idx_int(phases.swing_end, n_frames)
    return s, e


def _clip_idx_int(idx: int, n_frames: int) -> int:
    return max(0, min(idx, n_frames - 1))


# ==================== 4 个推杆特征 ====================


def feat_pendulum_stability(keypoints: np.ndarray, phases: PuttingPhaseResult) -> float:
    """双肩中点 y 在整段挥动的方差（越小越稳）。"""
    n = len(keypoints)
    s, e = _swing_window(phases, n)
    if e <= s:
        raise ValueError("空挥动窗口")
    seg = keypoints[s : e + 1]
    l_y = seg[:, LANDMARK_LEFT_SHOULDER, 1]
    r_y = seg[:, LANDMARK_RIGHT_SHOULDER, 1]
    shoulder_mid_y = (l_y + r_y) / 2.0
    return float(np.var(shoulder_mid_y))


def feat_head_stability(keypoints: np.ndarray, phases: PuttingPhaseResult) -> float:
    """鼻关键点 2D 位移方差 = var(x) + var(y)（越小越稳）。"""
    n = len(keypoints)
    s, e = _swing_window(phases, n)
    if e <= s:
        raise ValueError("空挥动窗口")
    nose = keypoints[s : e + 1, LANDMARK_NOSE, :2]
    return float(np.var(nose[:, 0]) + np.var(nose[:, 1]))


def feat_face_alignment(keypoints: np.ndarray, phases: PuttingPhaseResult) -> float:
    """击球点处握把线偏离「方正」的角度（度，越小越好）。

    - 击球方向 = 主腕从 backstroke 起点到 impact 的位移向量
    - 推杆面朝向代理 = 击球帧双腕连线（M7-09 杆追踪到位后替换为真实杆面）
    - 方正 = 握把线 ⊥ 击球方向（夹角 90°）；返回 |90 - 夹角|
    """
    impact = _clip_idx(keypoints, phases.impact_frame)
    bs_start = _clip_idx(keypoints, phases.phases["backstroke"].start_frame)
    lead = phases.lead_wrist_idx

    stroke = keypoints[impact, lead, :2] - keypoints[bs_start, lead, :2]
    if float(np.linalg.norm(stroke)) < 1e-4:
        raise ValueError("击球方向位移过小")

    hand_line = (
        keypoints[impact, LANDMARK_RIGHT_WRIST, :2]
        - keypoints[impact, LANDMARK_LEFT_WRIST, :2]
    )
    if float(np.linalg.norm(hand_line)) < 1e-4:
        raise ValueError("双腕连线过短")

    angle = _angle_2d_deg(hand_line, stroke)  # [0, 180]
    return abs(90.0 - angle)  # 方正→0；与击球方向平行→90


def feat_tempo_ratio(keypoints: np.ndarray, phases: PuttingPhaseResult) -> float:
    """backstroke 时长 / forward stroke 时长（帧数比）。"""
    bs = phases.phases["backstroke"]
    backstroke_frames = bs.end_frame - bs.start_frame
    forward_frames = phases.impact_frame - bs.end_frame
    if forward_frames <= 0 or backstroke_frames <= 0:
        raise ValueError("阶段帧数非法")
    return float(backstroke_frames / forward_frames)


_PUTTING_FEATURE_FUNCS = {
    "pendulum_stability": feat_pendulum_stability,
    "head_stability": feat_head_stability,
    "face_alignment": feat_face_alignment,
    "tempo_ratio": feat_tempo_ratio,
}

assert set(_PUTTING_FEATURE_FUNCS) == {f["name"] for f in PUTTING_FEATURES}, (
    "putting.features._PUTTING_FEATURE_FUNCS 与 constants.PUTTING_FEATURES 不同步"
)


def extract_putting_features(
    keypoints: np.ndarray, phases: PuttingPhaseResult
) -> dict[str, float]:
    """批量跑 4 个推杆特征。算不出来时退化为该特征 ideal 中点（不崩、不误报）。"""
    out: dict[str, float] = {}
    for name, fn in _PUTTING_FEATURE_FUNCS.items():
        try:
            value = float(fn(keypoints, phases))
            if not np.isfinite(value):
                raise ValueError(f"{name} 返回非有限值")
            out[name] = value
        except Exception as exc:  # noqa: BLE001
            meta = putting_feature_meta(name)
            fallback = (meta["ideal_min"] + meta["ideal_max"]) / 2.0
            log.warning(
                "putting_feature_fallback",
                extra={"feature": name, "error": str(exc), "fallback": fallback},
            )
            out[name] = fallback
    return out
