"""P2-M7-12 · 切杆 4 阶段分割（setup → backswing → impact → follow）。

半挥切杆：幅度介于推杆与全挥之间（``CHIPPING_MIN_MOTION_SPEED=0.005``）。
算法：
1. lead 腕速度活跃窗口定 swing_start/end。
2. backswing 顶点 = 窗口内 lead 腕 y 最小（最高位）。
3. impact = 顶点之后速度峰值帧。
4. setup/follow 各取 ~0.5s。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.errors import NoSwingError
from app.pipeline.pose import (
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
    PoseResult,
)
from app.pipeline.chipping.constants import CHIPPING_PHASE_ORDER

log = logging.getLogger("ai_engine.chipping.phases")

CHIPPING_MIN_MOTION_SPEED = 0.005
MIN_CHIPPING_FRAMES = 12
MIN_CHIPPING_SWING_FRAMES = 8


@dataclass
class ChippingPhaseInfo:
    start_frame: int
    end_frame: int
    key_frame: int

    def start_time(self, fps: float) -> float:
        return self.start_frame / fps

    def end_time(self, fps: float) -> float:
        return self.end_frame / fps


@dataclass
class ChippingPhaseResult:
    phases: dict[str, ChippingPhaseInfo]
    impact_frame: int
    top_frame: int
    swing_start: int
    swing_end: int
    lead_wrist_idx: int
    lead_shoulder_idx: int
    handedness: Literal["right", "left"]
    fps: float

    def __post_init__(self) -> None:
        missing = set(CHIPPING_PHASE_ORDER) - set(self.phases)
        if missing:
            raise ValueError(f"ChippingPhaseResult.phases 缺阶段 {sorted(missing)}")


def _wrist_speed(keypoints: np.ndarray, valid_mask: np.ndarray, wrist_idx: int) -> np.ndarray:
    wrists = keypoints[:, wrist_idx, :2]
    speeds = np.zeros(len(wrists), dtype=np.float32)
    for i in range(1, len(wrists)):
        if valid_mask[i] and valid_mask[i - 1]:
            speeds[i] = float(np.linalg.norm(wrists[i] - wrists[i - 1]))
    return speeds


def _choose_lead_side(
    keypoints: np.ndarray, valid_mask: np.ndarray
) -> tuple[Literal["right", "left"], int, int]:
    if valid_mask.sum() < 2:
        return "right", LANDMARK_LEFT_WRIST, LANDMARK_LEFT_SHOULDER
    lw = keypoints[valid_mask, LANDMARK_LEFT_WRIST, :2]
    rw = keypoints[valid_mask, LANDMARK_RIGHT_WRIST, :2]
    if float(np.linalg.norm(lw.max(axis=0) - lw.min(axis=0))) >= float(
        np.linalg.norm(rw.max(axis=0) - rw.min(axis=0))
    ):
        return "right", LANDMARK_LEFT_WRIST, LANDMARK_LEFT_SHOULDER
    return "left", LANDMARK_RIGHT_WRIST, LANDMARK_RIGHT_SHOULDER


def _find_active_window(speeds: np.ndarray) -> tuple[int, int]:
    active = speeds > CHIPPING_MIN_MOTION_SPEED
    if not active.any():
        return -1, -1
    idx = np.where(active)[0]
    start, end = int(idx[0]), int(idx[-1])
    if end - start < MIN_CHIPPING_SWING_FRAMES:
        return -1, -1
    return start, end


def segment_chipping_phases(pose: PoseResult) -> ChippingPhaseResult:
    """切杆 4 阶段分割。"""
    keypoints = pose.keypoints
    valid_mask = pose.valid_mask
    fps = pose.fps
    num_frames = pose.num_frames

    if num_frames < MIN_CHIPPING_FRAMES:
        raise NoSwingError(
            f"视频帧数 {num_frames} < 最小切杆帧数 {MIN_CHIPPING_FRAMES}",
            user_message="视频太短，请录制完整的切杆动作",
        )

    handedness, lead_wrist_idx, lead_shoulder_idx = _choose_lead_side(keypoints, valid_mask)
    speeds = _wrist_speed(keypoints, valid_mask, lead_wrist_idx)
    swing_start, swing_end = _find_active_window(speeds)
    if swing_start < 0:
        raise NoSwingError(
            "未检测到明显切杆动作",
            user_message="未检测到切杆动作，请确保半挥完整",
        )

    wrist_y = keypoints[:, lead_wrist_idx, 1]
    mask = np.zeros(num_frames, dtype=bool)
    mask[swing_start : swing_end + 1] = True
    search = mask & valid_mask
    if not search.any():
        search = mask
    top_frame = int(np.argmin(np.where(search, wrist_y, np.inf)))
    if top_frame <= swing_start:
        top_frame = swing_start + max(1, (swing_end - swing_start) // 3)
    if top_frame >= swing_end - 2:
        top_frame = swing_end - max(2, (swing_end - swing_start) // 5)

    post_top = speeds[top_frame : swing_end + 1]
    impact_frame = top_frame + int(np.argmax(post_top)) if len(post_top) else top_frame + 1
    impact_frame = max(top_frame + 1, min(impact_frame, swing_end))

    setup_pre = int(round(fps * 0.5))
    setup_start = max(0, swing_start - setup_pre)
    setup_end = max(setup_start, swing_start - 1)
    follow_post = int(round(fps * 0.5))
    follow_end = min(num_frames - 1, swing_end + follow_post)

    phases: dict[str, ChippingPhaseInfo] = {
        "setup": ChippingPhaseInfo(setup_start, setup_end, setup_end),
        "backswing": ChippingPhaseInfo(
            swing_start, max(swing_start, top_frame - 1), top_frame
        ),
        "impact": ChippingPhaseInfo(impact_frame, impact_frame, impact_frame),
        "follow": ChippingPhaseInfo(
            min(impact_frame + 1, follow_end),
            follow_end,
            min(impact_frame + 1 + (follow_end - impact_frame) // 2, follow_end),
        ),
    }

    return ChippingPhaseResult(
        phases=phases,
        impact_frame=impact_frame,
        top_frame=top_frame,
        swing_start=swing_start,
        swing_end=swing_end,
        lead_wrist_idx=lead_wrist_idx,
        lead_shoulder_idx=lead_shoulder_idx,
        handedness=handedness,
        fps=fps,
    )
