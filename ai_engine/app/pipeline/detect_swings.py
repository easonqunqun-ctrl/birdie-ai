"""P2-M7-13 · 多挥候选探测（预处理 + pose + detect，不跑评分/诊断）。"""

from __future__ import annotations

import logging
import time

from app.errors import MultiSwingOverflowError, PipelineError
from app.pipeline.multi_swing import (
    default_swing_index,
    detect_swing_candidates,
)
from app.pipeline.pose import estimate_poses
from app.pipeline.preprocess import preprocess_video
from app.pipeline.swing_candidate_previews import build_swing_candidate_items
from app.schemas import DetectSwingsRequest, DetectSwingsResult

log = logging.getLogger("ai_engine.detect_swings")


def run_detect_swings(req: DetectSwingsRequest) -> DetectSwingsResult:
    """同步 CPU/IO 密集；由 FastAPI 路由 ``async def`` 直接调用（与 analyze 一致）。"""
    t0 = time.perf_counter()
    log.info(
        "detect_swings_start",
        extra={"analysis_id": req.analysis_id, "video_url": req.video_url},
    )
    try:
        pre = preprocess_video(req.video_url)
        fps = pre.fps
        pose_result = estimate_poses(pre.normalized_video_path)
        raw = detect_swing_candidates(pose_result)
        if len(raw) > 5:
            raise MultiSwingOverflowError(
                f"检测到 {len(raw)} 段挥杆，超过上限 5"
            )
        candidates = build_swing_candidate_items(
            analysis_id=req.analysis_id,
            normalized_video_path=pre.normalized_video_path,
            raw=raw,
            fps=fps,
        )
        default_idx = default_swing_index(raw) if raw else 0
        log.info(
            "detect_swings_done",
            extra={
                "analysis_id": req.analysis_id,
                "count": len(candidates),
                "default_index": default_idx,
                "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
            },
        )
        return DetectSwingsResult(
            analysis_id=req.analysis_id,
            status="ok",
            swing_candidates=candidates,
            default_selected_index=default_idx,
        )
    except PipelineError as exc:
        log.warning(
            "detect_swings_failed",
            extra={"analysis_id": req.analysis_id, "code": exc.code, "error": str(exc)},
        )
        return DetectSwingsResult(
            analysis_id=req.analysis_id,
            status="failed",
            error_code=exc.code,
            error_message=exc.user_message,
        )
