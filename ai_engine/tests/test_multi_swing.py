"""P2-M7-13 · 多挥识别 + 试挥判别单测。"""

from __future__ import annotations

import numpy as np
import pytest

from app.errors import MultiSwingOverflowError
from app.pipeline.pose import (
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
    PoseResult,
)
from app.pipeline.multi_swing import (
    MAX_SWING_CANDIDATES,
    MIN_INTER_SWING_IDLE_FRAMES,
    SwingCandidate,
    default_swing_index,
    detect_swing_candidates,
    find_swing_windows,
    merge_intr_swing_split_windows,
    resolve_swing_selection,
    segment_phases_with_multi_swing,
)
from app.pipeline.phases import MIN_MOTION_SPEED, MIN_SWING_FRAMES, SWING_END_IDLE_FRAMES

_FPS = 30.0


def _fill_static_body(kp: np.ndarray) -> None:
    kp[:, :, 2] = 1.0
    kp[:, LANDMARK_LEFT_SHOULDER, :2] = (0.45, 0.40)
    kp[:, LANDMARK_RIGHT_SHOULDER, :2] = (0.55, 0.40)
    kp[:, LANDMARK_RIGHT_WRIST, :2] = (0.52, 0.55)


def _paint_swing_segment(
    kp: np.ndarray,
    start: int,
    end: int,
    *,
    step: float,
    lead: int = LANDMARK_LEFT_WRIST,
) -> None:
    """逐帧固定步长位移，保证连续活跃帧数 ≥ MIN_SWING_FRAMES。"""
    rest = np.array([0.48, 0.58], dtype=np.float32)
    length = end - start
    top = start + length // 3
    impact = start + (2 * length) // 3
    settle = end - 3

    pos = rest.copy()
    kp[start, lead, :2] = pos
    for i in range(start + 1, end + 1):
        if i > settle:
            kp[i, lead, :2] = rest
            continue
        if i <= top:
            delta = np.array([-step * 0.72, -step * 0.72], dtype=np.float32)
        elif i <= impact:
            delta = np.array([step * 0.88, step * 0.88], dtype=np.float32)
        else:
            delta = np.array([step * 0.35, step * 0.30], dtype=np.float32)
        pos = pos + delta
        kp[i, lead, :2] = pos


def _make_multi_swing_pose(n: int = 200) -> PoseResult:
    kp = np.zeros((n, 33, 3), dtype=np.float32)
    _fill_static_body(kp)
    kp[:, LANDMARK_LEFT_WRIST, :2] = (0.48, 0.58)
    _paint_swing_segment(kp, 15, 50, step=0.012)
    kp[51:118, LANDMARK_LEFT_WRIST, :2] = (0.48, 0.58)
    _paint_swing_segment(kp, 118, 168, step=0.028)
    return PoseResult(
        keypoints=kp,
        visibility=np.ones((n, 33), dtype=np.float32),
        valid_mask=np.ones(n, dtype=bool),
        num_frames=n,
        fps=_FPS,
    )


def _speeds_three_swings() -> np.ndarray:
    n = 200
    speeds = np.zeros(n, dtype=np.float32)
    speeds[10:41] = 0.012
    speeds[70:101] = 0.011
    speeds[130:171] = 0.025
    speeds[155] = 0.04
    return speeds


def test_find_swing_windows_finds_three() -> None:
    windows = find_swing_windows(
        _speeds_three_swings(),
        min_speed=MIN_MOTION_SPEED,
        min_frames=MIN_SWING_FRAMES,
        gap_frames=SWING_END_IDLE_FRAMES,
    )
    assert len(windows) == 3
    merged = merge_intr_swing_split_windows(windows)
    assert len(merged) == 3


def test_merge_top_of_swing_valley_false_split() -> None:
    """顶点速度低于阈值时不应把一次挥杆切成两段。"""
    n = 90
    speeds = np.zeros(n, dtype=np.float32)
    speeds[10:27] = 0.015
    speeds[27:39] = 0.002
    speeds[39:58] = 0.018
    speeds[58] = 0.025

    raw = find_swing_windows(speeds)
    assert len(raw) == 2
    merged = merge_intr_swing_split_windows(raw)
    assert merged == [(10, 58)]


def test_detect_single_swing_after_top_valley_merge() -> None:
    n = 90
    kp = np.zeros((n, 33, 3), dtype=np.float32)
    _fill_static_body(kp)
    kp[:, LANDMARK_LEFT_WRIST, :2] = (0.48, 0.58)
    _paint_swing_segment(kp, 10, 58, step=0.022)
    pose = PoseResult(
        keypoints=kp,
        visibility=np.ones((n, 33), dtype=np.float32),
        valid_mask=np.ones(n, dtype=bool),
        num_frames=n,
        fps=_FPS,
    )
    cands = detect_swing_candidates(pose)
    assert len(cands) == 1
    assert not cands[0].is_practice


def test_inter_swing_idle_threshold_between_split_and_multi() -> None:
    """真·两次挥杆 idle ≥ MIN_INTER_SWING_IDLE_FRAMES 时不合并。"""
    assert MIN_INTER_SWING_IDLE_FRAMES == 20
    windows = [(10, 40), (61, 90)]
    assert merge_intr_swing_split_windows(windows) == [(10, 40), (61, 90)]


def test_practice_swing_classified_by_low_peak() -> None:
    cands = detect_swing_candidates(_make_multi_swing_pose())
    assert len(cands) >= 2
    assert any(c.is_practice for c in cands)
    assert any(not c.is_practice for c in cands)
    assert not cands[default_swing_index(cands)].is_practice


def test_default_swing_index_picks_first_non_practice() -> None:
    cands = [
        SwingCandidate(0, 30, True, 0.8, 0.01, 15, 25),
        SwingCandidate(50, 80, True, 0.75, 0.01, 65, 75),
        SwingCandidate(100, 140, False, 0.92, 0.03, 120, 130),
    ]
    assert default_swing_index(cands) == 2


def test_resolve_raises_50122_when_over_5() -> None:
    cands = [
        SwingCandidate(i * 30, i * 30 + 20, False, 0.9, 0.02, i * 30 + 10, i * 30 + 15)
        for i in range(MAX_SWING_CANDIDATES + 1)
    ]
    with pytest.raises(MultiSwingOverflowError):
        resolve_swing_selection(cands, None)


def test_segment_phases_with_multi_swing_end_to_end() -> None:
    phases, cands, idx = segment_phases_with_multi_swing(_make_multi_swing_pose())
    assert phases.impact_frame > phases.top_frame
    assert len(cands) >= 2
    assert not cands[idx].is_practice


def test_single_swing_still_segments() -> None:
    n = 60
    kp = np.zeros((n, 33, 3), dtype=np.float32)
    _fill_static_body(kp)
    kp[:, LANDMARK_LEFT_WRIST, :2] = (0.48, 0.58)
    _paint_swing_segment(kp, 8, 48, step=0.022)
    pose = PoseResult(
        keypoints=kp,
        visibility=np.ones((n, 33), dtype=np.float32),
        valid_mask=np.ones(n, dtype=bool),
        num_frames=n,
        fps=_FPS,
    )
    phases, cands, idx = segment_phases_with_multi_swing(pose)
    assert phases.swing_end >= phases.swing_start
    assert idx == 0
