"""P2-M7-13 · 试挥 / 多挥杆识别（启发式，纯逻辑）。

基于 lead 腕速度时序切分多段活跃窗口，判别试挥（速度峰低 / follow 不完整），
默认选第一段非试挥；>5 段抛 ``MultiSwingOverflowError``（50122）。

客户端 select-swing UI / 缩略图生成挂 M10（wait-for-triggers）；本模块供
``real_pipeline`` full_swing 路径集成。

详 ``docs/release-notes/p2-m7-13-multi-swing-detection-kickoff.md`` §3。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from app.errors import MultiSwingOverflowError, NoSwingError
from app.pipeline.phases import (
    MIN_MOTION_SPEED,
    MIN_SWING_FRAMES,
    SWING_END_IDLE_FRAMES,
    PhaseSegmentResult,
    _choose_lead_side,
    _wrist_speed,
    segment_phases,
)
from app.pipeline.pose import PoseResult

log = logging.getLogger("ai_engine.multi_swing")

MAX_SWING_CANDIDATES = 5
# 候选峰速 < 全局峰速 × 此比例 → 试挥（kickoff §3.3 启发式）
PRACTICE_SPEED_RATIO = 0.55
# follow 段长度 < backswing × 此比例 → follow 不完整，倾向试挥
PRACTICE_FOLLOW_RATIO = 0.30


@dataclass
class SwingCandidate:
    """单段挥杆候选（kickoff §3.2）。"""

    start_frame: int
    end_frame: int
    is_practice: bool
    confidence: float
    speed_peak: float
    top_frame: int
    impact_frame: int

    def to_dict(self, fps: float) -> dict:
        return {
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "is_practice": self.is_practice,
            "confidence": round(self.confidence, 3),
            "start_time_sec": round(self.start_frame / fps, 2),
            "end_time_sec": round(self.end_frame / fps, 2),
        }


def find_swing_windows(
    speeds: np.ndarray,
    *,
    min_speed: float = MIN_MOTION_SPEED,
    min_frames: int = MIN_SWING_FRAMES,
    gap_frames: int = SWING_END_IDLE_FRAMES,
) -> list[tuple[int, int]]:
    """从速度序列切分多个活跃窗口（帧间 idle ≥ gap_frames 断开）。"""
    n = len(speeds)
    windows: list[tuple[int, int]] = []
    in_window = False
    start = 0
    gap = 0
    for i in range(n):
        if speeds[i] > min_speed:
            if not in_window:
                start = i
                in_window = True
            gap = 0
        elif in_window:
            gap += 1
            if gap >= gap_frames:
                end = i - gap
                if end - start >= min_frames:
                    windows.append((start, end))
                in_window = False
                gap = 0
    if in_window:
        end = n - 1
        while end > start and speeds[end] <= min_speed:
            end -= 1
        if end - start >= min_frames:
            windows.append((start, end))
    return windows


def _analyze_window(
    speeds: np.ndarray,
    keypoints: np.ndarray,
    window: tuple[int, int],
    lead_wrist_idx: int,
    global_peak: float,
) -> SwingCandidate:
    start, end = window
    seg_speeds = speeds[start : end + 1]
    peak = float(np.max(seg_speeds))

    wrist_y = keypoints[start : end + 1, lead_wrist_idx, 1]
    top_rel = int(np.argmin(wrist_y))
    top_frame = start + top_rel
    top_frame = max(start + 1, min(top_frame, end - 2))

    post_top = speeds[top_frame : end + 1]
    if len(post_top) > 0:
        impact_frame = top_frame + int(np.argmax(post_top))
    else:
        impact_frame = min(top_frame + 1, end)
    impact_frame = max(top_frame + 1, min(impact_frame, end))

    backswing_len = max(1, top_frame - start)
    follow_len = max(0, end - impact_frame)
    incomplete_follow = follow_len < backswing_len * PRACTICE_FOLLOW_RATIO
    low_peak = peak < global_peak * PRACTICE_SPEED_RATIO
    # 峰速明显低于全局峰 → 试挥；follow 不完整仅在与峰速偏低同时成立时加强判定
    is_practice = low_peak or (incomplete_follow and peak < global_peak * 0.80)

    conf = min(0.95, 0.55 + (peak / (global_peak + 1e-8)) * 0.4)
    if is_practice:
        conf = min(conf, 0.88)

    return SwingCandidate(
        start_frame=start,
        end_frame=end,
        is_practice=is_practice,
        confidence=conf,
        speed_peak=peak,
        top_frame=top_frame,
        impact_frame=impact_frame,
    )


def detect_swing_candidates(pose: PoseResult) -> list[SwingCandidate]:
    """检测视频中全部挥杆候选段。"""
    keypoints = pose.keypoints
    valid_mask = pose.valid_mask
    _, lead_wrist_idx, _ = _choose_lead_side(keypoints, valid_mask)
    speeds = _wrist_speed(keypoints, valid_mask, lead_wrist_idx)

    windows = find_swing_windows(speeds)
    if not windows:
        return []

    peaks = [float(np.max(speeds[s : e + 1])) for s, e in windows]
    global_peak = max(peaks)

    candidates = [
        _analyze_window(speeds, keypoints, w, lead_wrist_idx, global_peak) for w in windows
    ]
    log.info(
        "multi_swing_detected",
        extra={"count": len(candidates), "practice": sum(c.is_practice for c in candidates)},
    )
    return candidates


def default_swing_index(candidates: list[SwingCandidate]) -> int:
    """默认选第一段非试挥；全是试挥则选第一段（kickoff R-04）。"""
    for i, c in enumerate(candidates):
        if not c.is_practice:
            return i
    return 0


def resolve_swing_selection(
    candidates: list[SwingCandidate],
    selected_swing_index: int | None,
) -> tuple[int, SwingCandidate]:
    """解析用户选择或默认段；>5 段抛 50122。"""
    if len(candidates) > MAX_SWING_CANDIDATES:
        raise MultiSwingOverflowError(
            f"检测到 {len(candidates)} 段挥杆，超过上限 {MAX_SWING_CANDIDATES}"
        )
    if not candidates:
        raise NoSwingError(
            "未检测到挥杆候选段",
            user_message="未检测到挥杆动作，请确保动作完整",
        )
    if len(candidates) == 1:
        return 0, candidates[0]

    if selected_swing_index is not None:
        if not (0 <= selected_swing_index < len(candidates)):
            idx = default_swing_index(candidates)
            log.warning(
                "selected_swing_index_out_of_range",
                extra={"requested": selected_swing_index, "fallback": idx},
            )
        else:
            idx = selected_swing_index
    else:
        idx = default_swing_index(candidates)

    return idx, candidates[idx]


def segment_phases_with_multi_swing(
    pose: PoseResult,
    *,
    selected_swing_index: int | None = None,
) -> tuple[PhaseSegmentResult, list[SwingCandidate], int]:
    """多挥识别 + 对选中段做六阶段分割。

    Returns:
        (phases, all_candidates, selected_index)
    """
    candidates = detect_swing_candidates(pose)
    if not candidates:
        phases = segment_phases(pose)
        return phases, [], 0

    idx, chosen = resolve_swing_selection(candidates, selected_swing_index)
    phases = segment_phases(
        pose,
        swing_window=(chosen.start_frame, chosen.end_frame),
    )
    return phases, candidates, idx


def multi_swing_engine_warning(
    candidates: list[SwingCandidate], selected_index: int, fps: float
) -> dict | None:
    """多段时生成 engine_warning 文案（单段返回 None）。"""
    if len(candidates) <= 1:
        return None
    n = len(candidates)
    seg_no = selected_index + 1
    practice_n = sum(1 for c in candidates if c.is_practice)
    detail = (
        f"检测到 {n} 段挥杆（{practice_n} 段试挥），"
        f"已自动选择第 {seg_no} 段进行分析"
    )
    return {"code": "multi_swing_auto_selected", "level": "info", "detail": detail}
