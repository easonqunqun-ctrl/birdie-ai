"""P2-M7-11 · 推杆 4 阶段分割（W22 骨架；分割算法本体 W23）。

本文件 W22 只落 **数据结构骨架**（``PuttingPhaseInfo`` / ``PuttingPhaseResult``），
供 ``features.py`` 计算 4 个推杆特征时消费。真正的分割实现（手腕速度起停 + 峰值定
impact，kickoff §3.3）排 W23。

与 full_swing ``phases.PhaseSegmentResult`` 独立：推杆只有 4 阶段、无 top_frame。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.pipeline.putting.constants import PUTTING_PHASE_ORDER


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


def segment_putting_phases(*args, **kwargs):  # noqa: ANN002, ANN003, ANN201
    """推杆 4 阶段分割（W23 实现）。

    W22 仅骨架占位：手腕速度阈值定 backstroke 起点、峰值定 impact、衰减定 follow
    （kickoff §3.3）排 W23，连同硬约束（setup<backstroke<impact<follow）一起做。
    """
    raise NotImplementedError(
        "segment_putting_phases 排 P2-M7-11 W23；W22 仅交付特征 + 数据结构骨架"
    )
