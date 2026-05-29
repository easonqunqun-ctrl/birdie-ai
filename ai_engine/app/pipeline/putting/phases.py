"""P2-M7-11 W23 · 推杆 4 阶段分割（setup → backstroke → impact → follow）。

与 full_swing ``phases.PhaseSegmentResult`` 独立：推杆只有 4 阶段、无 top_frame，
动作幅度远小于全挥（阈值更低）。算法（kickoff §3.3）：

1. 主手选择：窗口内位移更大的腕为 lead（与 full_swing 同口径）。
2. 活跃窗口：lead 腕帧间速度 > ``PUTTING_MIN_MOTION_SPEED`` 的首/末帧。
3. impact：窗口内速度峰值帧（推杆向球加速到击球）。
4. backstroke 顶点：swing_start 与 impact 之间的**速度极小帧**（钟摆在回摆顶点瞬时停顿）。
5. setup/follow：窗口前后各取 ~0.5s。
硬约束：setup < backstroke < impact < follow。
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
from app.pipeline.putting.constants import PUTTING_PHASE_ORDER

log = logging.getLogger("ai_engine.putting.phases")

# ==================== 阈值（推杆幅度小，阈值低于 full_swing 0.008） ====================

# 帧间位移速度阈值（归一化坐标）：推杆腕速远低于全挥
PUTTING_MIN_MOTION_SPEED = 0.003
# 推杆最小帧数（约 0.3s @30fps；低于此大概率不是一次完整推击）
MIN_PUTTING_FRAMES = 10
# 活跃窗口最小跨度
MIN_PUTTING_SWING_FRAMES = 6


@dataclass
class PuttingPhaseInfo:
    """单个推杆阶段的时间区间（闭区间，与 full_swing PhaseInfo 同款约定）。"""

    start_frame: int
    end_frame: int
    key_frame: int

    def start_time(self, fps: float) -> float:
        return self.start_frame / fps

    def end_time(self, fps: float) -> float:
        return self.end_frame / fps


@dataclass
class PuttingPhaseResult:
    """推杆 4 阶段分割输出（kickoff §3.3）。

    Attributes:
        phases: dict[phase_key, PuttingPhaseInfo]，key 与 ``PUTTING_PHASE_ORDER`` 一致
        impact_frame: 击球帧（手腕速度峰值）
        swing_start / swing_end: 整段推击活跃区间（钟摆/头部稳定度按此窗口算）
        lead_wrist_idx / lead_shoulder_idx: 主侧关键点编号（与 full_swing 同口径）
        handedness: 右手 / 左手
        fps: 帧率
    """

    phases: dict[str, PuttingPhaseInfo]
    impact_frame: int
    swing_start: int
    swing_end: int
    lead_wrist_idx: int
    lead_shoulder_idx: int
    handedness: Literal["right", "left"]
    fps: float

    def __post_init__(self) -> None:
        missing = set(PUTTING_PHASE_ORDER) - set(self.phases)
        if missing:
            raise ValueError(f"PuttingPhaseResult.phases 缺阶段 {sorted(missing)}")


# ==================== 辅助函数 ====================


def _wrist_speed(keypoints: np.ndarray, valid_mask: np.ndarray, wrist_idx: int) -> np.ndarray:
    """lead 腕逐帧位移速度（归一化坐标）；无效帧速度填 0。第 0 帧速度定义为 0。"""
    wrists = keypoints[:, wrist_idx, :2]
    speeds = np.zeros(len(wrists), dtype=np.float32)
    for i in range(1, len(wrists)):
        if not (valid_mask[i] and valid_mask[i - 1]):
            continue
        speeds[i] = float(np.linalg.norm(wrists[i] - wrists[i - 1]))
    return speeds


def _choose_lead_side(
    keypoints: np.ndarray, valid_mask: np.ndarray
) -> tuple[Literal["right", "left"], int, int]:
    """位移更大的腕为 lead（右撇子 → 左腕；与 full_swing 同口径）。"""
    if valid_mask.sum() < 2:
        return "right", LANDMARK_LEFT_WRIST, LANDMARK_LEFT_SHOULDER
    lw = keypoints[valid_mask, LANDMARK_LEFT_WRIST, :2]
    rw = keypoints[valid_mask, LANDMARK_RIGHT_WRIST, :2]
    l_range = float(np.linalg.norm(lw.max(axis=0) - lw.min(axis=0)))
    r_range = float(np.linalg.norm(rw.max(axis=0) - rw.min(axis=0)))
    if l_range >= r_range:
        return "right", LANDMARK_LEFT_WRIST, LANDMARK_LEFT_SHOULDER
    return "left", LANDMARK_RIGHT_WRIST, LANDMARK_RIGHT_SHOULDER


def _find_active_window(speeds: np.ndarray) -> tuple[int, int]:
    """速度 > 阈值的首/末帧；跨度不足返回 (-1, -1)。"""
    active = speeds > PUTTING_MIN_MOTION_SPEED
    if not active.any():
        return -1, -1
    idx = np.where(active)[0]
    start, end = int(idx[0]), int(idx[-1])
    if end - start < MIN_PUTTING_SWING_FRAMES:
        return -1, -1
    return start, end


# ==================== 主入口 ====================


def segment_putting_phases(pose: PoseResult) -> PuttingPhaseResult:
    """推杆 4 阶段分割。

    Raises:
        NoSwingError: 无明显推击动作（速度全程低于阈值或活跃区过短）。
    """
    keypoints = pose.keypoints
    valid_mask = pose.valid_mask
    fps = pose.fps
    num_frames = pose.num_frames

    if num_frames < MIN_PUTTING_FRAMES:
        raise NoSwingError(
            f"视频帧数 {num_frames} < 最小推杆帧数 {MIN_PUTTING_FRAMES}",
            user_message="视频太短，请录制完整的推杆动作",
        )

    handedness, lead_wrist_idx, lead_shoulder_idx = _choose_lead_side(keypoints, valid_mask)
    speeds = _wrist_speed(keypoints, valid_mask, lead_wrist_idx)
    swing_start, swing_end = _find_active_window(speeds)
    if swing_start < 0:
        raise NoSwingError(
            "未检测到明显推杆动作（手腕速度全程低于阈值）",
            user_message="未检测到推杆动作，请确保动作完整",
        )

    # impact = 窗口内速度峰值帧
    window_speeds = speeds[swing_start : swing_end + 1]
    impact_frame = swing_start + int(np.argmax(window_speeds))
    if impact_frame <= swing_start:
        impact_frame = min(swing_start + max(1, (swing_end - swing_start) // 2), swing_end)

    # backstroke 顶点 = swing_start 与 impact 之间速度极小帧（回摆顶点瞬时停顿）
    pause_seg = speeds[swing_start + 1 : impact_frame]
    if len(pause_seg) > 0:
        top_frame = swing_start + 1 + int(np.argmin(pause_seg))
    else:
        top_frame = swing_start + max(1, (impact_frame - swing_start) // 2)
    top_frame = max(swing_start + 1, min(top_frame, impact_frame - 1)) if impact_frame > swing_start + 1 else swing_start + 1

    setup_pre = int(round(fps * 0.5))
    setup_start = max(0, swing_start - setup_pre)
    setup_end = max(setup_start, swing_start - 1)
    follow_post = int(round(fps * 0.5))
    follow_end = min(num_frames - 1, swing_end + follow_post)

    phases: dict[str, PuttingPhaseInfo] = {
        "setup": PuttingPhaseInfo(setup_start, setup_end, setup_end),
        "backstroke": PuttingPhaseInfo(
            swing_start, max(swing_start, top_frame - 1), (swing_start + top_frame) // 2
        ),
        "impact": PuttingPhaseInfo(impact_frame, impact_frame, impact_frame),
        "follow": PuttingPhaseInfo(
            min(impact_frame + 1, follow_end),
            follow_end,
            min(impact_frame + 1 + (follow_end - impact_frame) // 2, follow_end),
        ),
    }

    log.info(
        "putting_phases_done",
        extra={
            "swing_start": swing_start,
            "swing_end": swing_end,
            "top_frame": top_frame,
            "impact_frame": impact_frame,
            "handedness": handedness,
        },
    )

    return PuttingPhaseResult(
        phases=phases,
        impact_frame=impact_frame,
        swing_start=swing_start,
        swing_end=swing_end,
        lead_wrist_idx=lead_wrist_idx,
        lead_shoulder_idx=lead_shoulder_idx,
        handedness=handedness,
        fps=fps,
    )
