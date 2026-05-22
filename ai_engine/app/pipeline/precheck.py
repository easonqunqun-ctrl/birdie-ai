"""O-08：上传后快速质量预检（≤5s 扫描预算，不含网络下载）。

在完整 `preprocess_video`（ffmpeg 转码）之前，对源视频做采样扫描，
与 preprocess 共用硬门槛 / 软警告阈值，供 `POST /precheck` 与 Celery 早失败。
"""

from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.errors import PipelineError, PoorQualityError, PreprocessError
from app.pipeline.preprocess import (
    MAX_DURATION_SEC,
    MAX_FRAME_LOSS_RATIO,
    MAX_LOW_CLARITY_FRAME_RATIO,
    MIN_CLARITY_SCORE,
    MIN_DURATION_SEC,
    MIN_QUALITY_SCORE,
    MIN_STABILITY_HARD_BLOCK,
    _ffprobe,
    _materialize_input,
    _quick_scan_quality,
    quality_warnings_from_scan,
)


@dataclass
class PrecheckResult:
    analysis_id: str
    status: Literal["passed", "blocked"]
    quality_warnings: list[str]
    error_code: int | None = None
    error_message: str | None = None
    elapsed_ms: int = 0
    scan_elapsed_ms: int = 0


def run_precheck(
    *,
    analysis_id: str,
    video_url: str,
    max_scan_sec: float = 5.0,
) -> PrecheckResult:
    """下载 + ffprobe + 快速扫描；扫描阶段受 ``max_scan_sec`` 约束。"""
    t0 = time.perf_counter()
    work_dir = Path(tempfile.mkdtemp(prefix="ai_engine_precheck_"))
    try:
        source_path = _materialize_input(video_url, work_dir)
        probe = _ffprobe(source_path)
        if probe.duration_sec < MIN_DURATION_SEC:
            raise PreprocessError(
                f"视频时长 {probe.duration_sec:.1f}s 不足 {MIN_DURATION_SEC}s",
                user_message=f"视频时长过短（至少需要 {int(MIN_DURATION_SEC)} 秒）",
            )
        if probe.duration_sec > MAX_DURATION_SEC:
            raise PreprocessError(
                f"视频时长 {probe.duration_sec:.1f}s 超过 {MAX_DURATION_SEC}s",
                user_message=f"视频时长过长（最多 {int(MAX_DURATION_SEC)} 秒）",
            )

        scan_t0 = time.perf_counter()
        stats = _quick_scan_quality(source_path, max_elapsed_sec=max_scan_sec)
        scan_elapsed_ms = int((time.perf_counter() - scan_t0) * 1000)

        _enforce_quality_gates(stats)
        warnings = quality_warnings_from_scan(stats)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return PrecheckResult(
            analysis_id=analysis_id,
            status="passed",
            quality_warnings=warnings,
            elapsed_ms=elapsed_ms,
            scan_elapsed_ms=scan_elapsed_ms,
        )
    except PipelineError as exc:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return PrecheckResult(
            analysis_id=analysis_id,
            status="blocked",
            quality_warnings=[],
            error_code=exc.code,
            error_message=exc.user_message,
            elapsed_ms=elapsed_ms,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _enforce_quality_gates(stats) -> None:
    if stats.clarity_score < MIN_CLARITY_SCORE:
        raise PoorQualityError(
            f"clarity_score={stats.clarity_score:.1f} < {MIN_CLARITY_SCORE}",
            user_message="视频画面过于模糊，请在光线充足的环境下重拍",
        )
    if stats.frame_loss_ratio > MAX_FRAME_LOSS_RATIO:
        raise PoorQualityError(
            f"frame_loss_ratio={stats.frame_loss_ratio:.2%}",
            user_message="视频解码异常，请重新上传",
        )
    if stats.low_clarity_frame_ratio > MAX_LOW_CLARITY_FRAME_RATIO:
        raise PoorQualityError(
            f"low_clarity_frame_ratio={stats.low_clarity_frame_ratio:.1%}",
            user_message="视频清晰度不稳定，请在光线充足、对焦清晰的环境下重拍",
        )
    if stats.stability_score < MIN_STABILITY_HARD_BLOCK:
        raise PoorQualityError(
            f"stability_score={stats.stability_score:.2f}",
            user_message="画面抖动过大，请固定机位或使用三脚架后重拍",
        )
    quality_score = _composite_quality_score(stats)
    if quality_score < MIN_QUALITY_SCORE:
        raise PoorQualityError(
            f"quality_score={quality_score:.2f} < {MIN_QUALITY_SCORE}",
            user_message="视频质量不足，请改善光线与机位后重拍",
        )


def _composite_quality_score(stats) -> float:
    import numpy as np

    clarity_component = min(stats.clarity_score / MIN_CLARITY_SCORE, 2.0) / 2.0
    stability_component = stats.stability_score
    frame_loss_penalty = max(0.0, 1.0 - stats.frame_loss_ratio / MAX_FRAME_LOSS_RATIO)
    score = 0.5 * clarity_component + 0.3 * stability_component + 0.2 * frame_loss_penalty
    return float(np.clip(score, 0.0, 1.0))
