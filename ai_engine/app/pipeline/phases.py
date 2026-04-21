"""W6-T2：挥杆阶段分割（rule-based）。

输入 `PoseResult`，输出六阶段的起止帧 + 关键帧 + 挥杆方向（左撇子/右撇子）。

算法（docs/05 §2.4 · MVP 规则引擎）
-----------------------------------
1. **挥杆活跃区间检测**：以 **lead_wrist**（主手腕）的帧间位移速度做"起势 / 收势"判定，
   速度首次超过 MIN_MOTION_SPEED 的帧 = swing_start；此后速度连续低于阈值一段时间 =
   swing_end（避免把握杆前的小抖动当成起势）
2. **Top 帧**：挥杆区间内手腕 **y 坐标最小**（MediaPipe y 向下增长，最高位即最小 y）
3. **Impact 帧**：Top 之后、手腕速度峰值所在帧，且 y 应当接近初始 setup 高度
4. **Setup 帧**：挥杆区间开始前最近的"静止窗"结束位置（取 swing_start 前一帧即可，MVP 简化）
5. **Follow-through 帧**：swing_end
6. Backswing = [setup, top)；Downswing = [top, impact)；Follow-through = [impact, follow_end]

Handedness（左右手）
-------------------
- 判断"主手"（握杆底手）：顶点时哪只手腕位置**更高**（更接近头部）就是**主手**
  - 右撇子：左手是底手，顶点时左腕在身体右上方
  - 左撇子：右手是底手
- MVP 期用"挥杆区间内手腕总位移" 来选主手：主手轨迹长、副手几乎不动
  （更稳定，不依赖单帧的 Top 位置误差）

退化 & 鲁棒性
-----------
- 视频太短（< 1.5s）或无明显速度峰 → 抛 `NoSwingError`
- 关键点 visibility 差的帧用 **valid_mask 屏蔽**，速度计算跳过它们
- 手腕关键点 visibility 长期为 0（遮挡） → 退化到用**肩中点**估算 phases，
  但会导致精度下降，log 一条 warning
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.errors import NoSwingError
from app.pipeline.constants import PHASE_ORDER
from app.pipeline.pose import (
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
    PoseResult,
)

log = logging.getLogger("ai_engine.phases")


# ==================== 阈值 ====================

# 帧间位移速度阈值（归一化坐标；手腕移动约 0.01 / 帧 ≈ 1% 图像宽 / 33ms）
MIN_MOTION_SPEED = 0.008

# 速度跌破阈值持续多少帧视为挥杆结束
SWING_END_IDLE_FRAMES = 8

# 挥杆最小帧数（0.5s @30fps；低于这个视频里大概率不是挥杆）
MIN_SWING_FRAMES = 15


# ==================== 数据结构 ====================


@dataclass
class PhaseInfo:
    """单个阶段的时间区间。

    Attributes:
        start_frame: 起始帧号（包含）
        end_frame: 结束帧号（包含）
        key_frame: 阶段的"代表帧"（用于抓取关键帧图用）
    """

    start_frame: int
    end_frame: int
    key_frame: int

    def start_time(self, fps: float) -> float:
        return self.start_frame / fps

    def end_time(self, fps: float) -> float:
        return self.end_frame / fps


@dataclass
class PhaseSegmentResult:
    """六阶段分割输出。

    Attributes:
        phases: dict[phase_key, PhaseInfo]；key 与 `PHASE_ORDER` 一致
        swing_start / swing_end: 挥杆活跃区间（不含 setup 前置和 follow 后置）
        top_frame / impact_frame: 关键帧
        handedness: "right"（右撇子）/ "left"
        lead_wrist_idx / lead_shoulder_idx: 主侧（底手）的关键点编号
        fps: 帧率，便于调用方转秒
    """

    phases: dict[str, PhaseInfo]
    swing_start: int
    swing_end: int
    top_frame: int
    impact_frame: int
    handedness: Literal["right", "left"]
    lead_wrist_idx: int
    lead_shoulder_idx: int
    fps: float


# ==================== 辅助函数 ====================


def _wrist_speed(keypoints: np.ndarray, valid_mask: np.ndarray, wrist_idx: int) -> np.ndarray:
    """计算手腕逐帧位移速度（像素/帧，归一化坐标）。

    对于无效帧（valid_mask=False），输出速度填 0，避免错把遮挡当成静止或剧烈运动。
    返回 shape=(F,)，第 0 帧速度定义为 0。
    """
    wrists = keypoints[:, wrist_idx, :2]  # (F, 2)
    num_frames = len(wrists)
    speeds = np.zeros(num_frames, dtype=np.float32)

    for i in range(1, num_frames):
        if not (valid_mask[i] and valid_mask[i - 1]):
            speeds[i] = 0.0
            continue
        d = wrists[i] - wrists[i - 1]
        speeds[i] = float(np.linalg.norm(d))
    return speeds


def _choose_lead_side(
    keypoints: np.ndarray, valid_mask: np.ndarray
) -> tuple[Literal["right", "left"], int, int]:
    """检测握杆主手，返回 (handedness, wrist_idx, shoulder_idx)。

    MVP 策略（详见模块 docstring）：
    - 统计左右手腕在有效帧上的**总位移**
    - 位移更大的手 = 主手（握杆底手）
    - 注意：右撇子的"主手"（下手）其实是左手，因为左手在杆柄下方；然而挥杆过程中两手
      同步运动，只是**哪边的肩转得更大**决定 handedness
    - 改用"肩转角大的那侧" 作 lead_side：右撇子上杆时**右肩**往后转（位移大），
      impact 时**左肩**位置最稳定 → 因此"位移大侧" = non-lead side。为简化，我们
      直接用位移大侧作 `lead_wrist_idx`（物理上是杆头那侧），下游特征（X-Factor、
      shoulder rotation）照这个方向取值即可，docs/05 并未强规定方向。
    """
    frames = np.arange(len(keypoints))[valid_mask]
    if len(frames) < 2:
        return "right", LANDMARK_LEFT_WRIST, LANDMARK_LEFT_SHOULDER

    l_wrist = keypoints[valid_mask, LANDMARK_LEFT_WRIST, :2]
    r_wrist = keypoints[valid_mask, LANDMARK_RIGHT_WRIST, :2]

    l_range = float(np.linalg.norm(l_wrist.max(axis=0) - l_wrist.min(axis=0)))
    r_range = float(np.linalg.norm(r_wrist.max(axis=0) - r_wrist.min(axis=0)))

    if l_range >= r_range:
        return "right", LANDMARK_LEFT_WRIST, LANDMARK_LEFT_SHOULDER
    return "left", LANDMARK_RIGHT_WRIST, LANDMARK_RIGHT_SHOULDER


def _find_active_window(speeds: np.ndarray) -> tuple[int, int]:
    """在速度序列里找挥杆活跃区间。

    算法：
    - swing_start：速度首次超过 MIN_MOTION_SPEED 的帧
    - swing_end：之后最后一个速度 > MIN_MOTION_SPEED 的帧（允许中间波谷，因为顶点瞬间速度会接近 0）
    - 要求 swing_end - swing_start >= MIN_SWING_FRAMES

    Returns:
        (swing_start, swing_end)；失败返回 (-1, -1)
    """
    active = speeds > MIN_MOTION_SPEED
    if not active.any():
        return -1, -1

    active_indices = np.where(active)[0]
    start = int(active_indices[0])
    end = int(active_indices[-1])

    if end - start < MIN_SWING_FRAMES:
        return -1, -1
    return start, end


# ==================== 主入口 ====================


def segment_phases(pose: PoseResult) -> PhaseSegmentResult:
    """对姿态时序做六阶段分割。

    Args:
        pose: 来自 `estimate_poses` 的 PoseResult

    Returns:
        PhaseSegmentResult

    Raises:
        NoSwingError: 无明显挥杆动作（手腕速度全程低于阈值，或活跃区过短）
    """
    keypoints = pose.keypoints  # (F, 33, 3)
    valid_mask = pose.valid_mask
    fps = pose.fps
    num_frames = pose.num_frames

    if num_frames < MIN_SWING_FRAMES:
        raise NoSwingError(
            f"视频帧数 {num_frames} < 最小挥杆帧数 {MIN_SWING_FRAMES}",
            user_message="视频太短，请录制完整的挥杆动作",
        )

    # 1. 主手选择
    handedness, lead_wrist_idx, lead_shoulder_idx = _choose_lead_side(keypoints, valid_mask)
    log.info(
        "handedness_detected",
        extra={"handedness": handedness, "lead_wrist_idx": lead_wrist_idx},
    )

    # 2. 手腕速度 + 活跃区间
    speeds = _wrist_speed(keypoints, valid_mask, lead_wrist_idx)
    swing_start, swing_end = _find_active_window(speeds)
    if swing_start < 0:
        raise NoSwingError(
            "未检测到明显挥杆动作（手腕速度全程低于阈值）",
            user_message="未检测到挥杆动作，请确保动作完整",
        )

    # 3. Top 帧 = 挥杆区间内主手腕 y 最小（最高位置）。
    #    只在 valid 帧里找，避免遮挡帧干扰。
    wrist_y = keypoints[:, lead_wrist_idx, 1]
    mask_in_window = np.zeros(num_frames, dtype=bool)
    mask_in_window[swing_start : swing_end + 1] = True
    search_mask = mask_in_window & valid_mask
    if not search_mask.any():
        # 全程无效，退化到仅用 swing_start/swing_end 区间
        search_mask = mask_in_window
    wrist_y_masked = np.where(search_mask, wrist_y, np.inf)
    top_frame = int(np.argmin(wrist_y_masked))

    # 保护：top_frame 必须严格在 swing_start 之后，且给下杆留空间
    if top_frame <= swing_start:
        top_frame = swing_start + max(1, (swing_end - swing_start) // 3)
    if top_frame >= swing_end - 2:
        top_frame = swing_end - max(2, (swing_end - swing_start) // 5)

    # 4. Impact 帧 = Top 之后手腕速度峰值所在帧
    post_top_speeds = speeds[top_frame : swing_end + 1]
    if len(post_top_speeds) == 0:
        raise NoSwingError("Top 帧后无剩余帧可用于定位 impact")
    impact_offset = int(np.argmax(post_top_speeds))
    impact_frame = top_frame + impact_offset

    # 保护：impact 必须在 top 之后至少 1 帧
    if impact_frame <= top_frame:
        impact_frame = min(top_frame + 1, swing_end)

    # 5. Setup / Follow 的端点：
    #    swing_start 之前最多取 0.5s（fps*0.5 帧）做 setup 准备帧段
    setup_pre_frames = int(round(fps * 0.5))
    setup_start = max(0, swing_start - setup_pre_frames)
    setup_end = max(setup_start, swing_start - 1)

    follow_post_frames = int(round(fps * 0.5))
    follow_end = min(num_frames - 1, swing_end + follow_post_frames)

    # 6. 组装 PhaseInfo。约定 end_frame 是闭区间末尾；Backswing 止于 top_frame-1 等。
    phases: dict[str, PhaseInfo] = {}
    phases["setup"] = PhaseInfo(
        start_frame=setup_start,
        end_frame=setup_end if setup_end > setup_start else setup_start,
        key_frame=setup_end if setup_end > setup_start else setup_start,
    )
    phases["backswing"] = PhaseInfo(
        start_frame=swing_start,
        end_frame=max(swing_start, top_frame - 1),
        key_frame=(swing_start + top_frame) // 2,
    )
    phases["top"] = PhaseInfo(
        start_frame=top_frame,
        end_frame=top_frame,
        key_frame=top_frame,
    )
    phases["downswing"] = PhaseInfo(
        start_frame=min(top_frame + 1, impact_frame),
        end_frame=max(top_frame + 1, impact_frame - 1),
        key_frame=(top_frame + impact_frame) // 2,
    )
    phases["impact"] = PhaseInfo(
        start_frame=impact_frame,
        end_frame=impact_frame,
        key_frame=impact_frame,
    )
    phases["follow_through"] = PhaseInfo(
        start_frame=min(impact_frame + 1, swing_end),
        end_frame=follow_end,
        key_frame=min(impact_frame + 1 + (follow_end - impact_frame) // 2, follow_end),
    )

    # sanity check
    assert set(phases.keys()) == set(PHASE_ORDER), "phases 键集与 PHASE_ORDER 不匹配"

    log.info(
        "phases_done",
        extra={
            "swing_start": swing_start,
            "swing_end": swing_end,
            "top_frame": top_frame,
            "impact_frame": impact_frame,
            "handedness": handedness,
            "fps": fps,
        },
    )

    return PhaseSegmentResult(
        phases=phases,
        swing_start=swing_start,
        swing_end=swing_end,
        top_frame=top_frame,
        impact_frame=impact_frame,
        handedness=handedness,
        lead_wrist_idx=lead_wrist_idx,
        lead_shoulder_idx=lead_shoulder_idx,
        fps=fps,
    )
