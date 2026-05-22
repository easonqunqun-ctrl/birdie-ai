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

from app.errors import PipelineError, PreprocessError
from app.pipeline.preprocess import (
    MAX_DURATION_SEC,
    MIN_DURATION_SEC,
    _ffprobe,
    _materialize_input,
    _quick_scan_quality,
    enforce_quality_gates,
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

        enforce_quality_gates(stats)
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
