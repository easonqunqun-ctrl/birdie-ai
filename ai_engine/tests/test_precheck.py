"""precheck.py 单元 / 集成测试."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.errors import PoorQualityError
from app.pipeline.preprocess import (
    MIN_STABILITY_HARD_BLOCK,
    _ScanStats,
    _scan_stats_from_samples,
    composite_quality_score,
    enforce_quality_gates,
)
from app.pipeline.precheck import run_precheck
from tests.conftest import needs_cv2, needs_ffmpeg


def test_composite_quality_score_clamps() -> None:
    stats = _ScanStats(
        fps=30.0,
        num_frames=90,
        width=720,
        height=1280,
        clarity_score=160.0,
        stability_score=0.9,
        frame_loss_ratio=0.0,
        low_clarity_frame_ratio=0.0,
    )
    assert composite_quality_score(stats) >= 0.5


def test_quick_scan_partial_sample_does_not_inflate_frame_loss() -> None:
    """precheck 只采样部分帧；不得把 CAP_PROP_FRAME_COUNT 与采样数之差当成解码丢帧。"""
    stats = _scan_stats_from_samples(
        fps=30.0,
        width=1080,
        height=1920,
        total_frames_hint=300,
        read_ok=25,
        read_fail=0,
        clarity_values=[200.0] * 25,
        diff_values=[5.0] * 24,
        partial_scan=True,
    )
    assert stats.frame_loss_ratio == 0.0
    enforce_quality_gates(stats)


def test_enforce_quality_gates_blocks_low_stability() -> None:
    stats = _ScanStats(
        fps=30.0,
        num_frames=30,
        width=720,
        height=1280,
        clarity_score=200.0,
        stability_score=MIN_STABILITY_HARD_BLOCK - 0.01,
        frame_loss_ratio=0.0,
        low_clarity_frame_ratio=0.0,
    )
    with pytest.raises(PoorQualityError) as exc_info:
        enforce_quality_gates(stats)
    assert "抖动" in exc_info.value.user_message


@needs_ffmpeg
@needs_cv2
def test_run_precheck_blocks_blackscreen(blackscreen_video: Path) -> None:
    result = run_precheck(
        analysis_id="test_precheck_black",
        video_url=str(blackscreen_video),
    )
    assert result.status == "blocked"
    assert result.error_code == 50102
    assert result.scan_elapsed_ms >= 0


@needs_ffmpeg
@needs_cv2
def test_run_precheck_passes_bouncing_box(bouncing_box_video: Path) -> None:
    result = run_precheck(
        analysis_id="test_precheck_ok",
        video_url=str(bouncing_box_video),
    )
    assert result.status == "passed"
    assert result.error_code is None
    assert result.scan_elapsed_ms >= 0
