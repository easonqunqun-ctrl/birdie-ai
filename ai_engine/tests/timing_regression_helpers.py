"""P2-M7-R1-B7 · preprocess V1/V2 阶段时刻对齐 helper（AC-B7 timing 回归）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.pipeline.multi_swing import segment_phases_with_multi_swing
from app.pipeline.phases import PhaseSegmentResult
from app.pipeline.pose import estimate_poses
from app.pipeline.pose_denoise import denoise_pose_result
from app.pipeline.pose_refine import refine_pose_result
from app.pipeline.preprocess import PreprocessResult, preprocess_video
from app.pipeline.preprocess_v2 import preprocess_video_v2

PHASE_TIMING_KEYS = ("top", "impact", "swing_start", "swing_end")

# B7 灰度开 flag 前：真视频 top/impact 时刻差应 < 250ms（约 30fps 下 7–8 帧）
DEFAULT_MAX_PHASE_DELTA_SEC = 0.25


@dataclass(frozen=True)
class PhaseTimingSnapshot:
    fps: float
    times_sec: dict[str, float]


def phase_key_times_sec(phases: PhaseSegmentResult, fps: float) -> dict[str, float]:
    """关键事件帧 → 秒（与 fps 归一化，便于跨 30/60fps 对比）。"""
    if fps <= 0:
        raise ValueError("fps must be positive")
    return {
        "top": phases.top_frame / fps,
        "impact": phases.impact_frame / fps,
        "swing_start": phases.swing_start / fps,
        "swing_end": phases.swing_end / fps,
    }


def phase_timing_deltas_sec(
    times_a: dict[str, float],
    times_b: dict[str, float],
    *,
    keys: tuple[str, ...] = PHASE_TIMING_KEYS,
) -> dict[str, float]:
    return {k: abs(times_a[k] - times_b[k]) for k in keys}


def phases_from_preprocessed(pre: PreprocessResult) -> PhaseSegmentResult:
    """preprocess 产物 → pose → phases（与 analyze 主链一致，不含 rotation/scoring）。"""
    pose_result = refine_pose_result(
        denoise_pose_result(estimate_poses(pre.normalized_video_path))
    )
    phases, _, _ = segment_phases_with_multi_swing(pose_result)
    return phases


def compare_preprocess_v1_v2_timing(
    video_path: Path | str,
    *,
    max_delta_sec: float = DEFAULT_MAX_PHASE_DELTA_SEC,
) -> tuple[PhaseTimingSnapshot, PhaseTimingSnapshot, dict[str, float]]:
    """同一源视频跑 V1/V2 preprocess + phases；返回快照与逐事件 Δt（秒）。"""
    path = str(video_path)
    pre_v1 = preprocess_video(path)
    pre_v2 = preprocess_video_v2(path)
    phases_v1 = phases_from_preprocessed(pre_v1)
    phases_v2 = phases_from_preprocessed(pre_v2)
    snap_v1 = PhaseTimingSnapshot(
        fps=pre_v1.fps,
        times_sec=phase_key_times_sec(phases_v1, pre_v1.fps),
    )
    snap_v2 = PhaseTimingSnapshot(
        fps=pre_v2.fps,
        times_sec=phase_key_times_sec(phases_v2, pre_v2.fps),
    )
    deltas = phase_timing_deltas_sec(snap_v1.times_sec, snap_v2.times_sec)
    over = {k: v for k, v in deltas.items() if v > max_delta_sec}
    if over:
        raise AssertionError(
            f"phase timing delta exceeded {max_delta_sec}s: {over} "
            f"(v1 fps={snap_v1.fps} v2 fps={snap_v2.fps})"
        )
    return snap_v1, snap_v2, deltas
