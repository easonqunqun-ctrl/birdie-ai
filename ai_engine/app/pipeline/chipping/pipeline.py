"""P2-M7-12 · 切杆 mode 真实分析编排。"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from app.pipeline.pose import estimate_poses, quality_warnings_from_pose
from app.pipeline.preprocess import preprocess_video, quality_warnings_from_preprocess
from app.pipeline.chipping.constants import CHIPPING_PHASE_LABELS, CHIPPING_PHASE_ORDER
from app.pipeline.chipping.diagnose import diagnose_chipping
from app.pipeline.chipping.features import extract_chipping_features
from app.pipeline.chipping.phases import segment_chipping_phases
from app.pipeline.chipping.scoring import score_chipping
from app.pipeline.real_pipeline import _merge_quality_warnings, _produce_derived_assets
from app.schemas import AnalyzeRequest, AnalyzeResult, IssueItem, PhaseScore

log = logging.getLogger("ai_engine.chipping.pipeline")


async def run_chipping_analysis(req: AnalyzeRequest) -> AnalyzeResult:
    t0 = time.perf_counter()
    pre = preprocess_video(req.video_url)
    pose_result = estimate_poses(pre.normalized_video_path)
    quality_warnings = _merge_quality_warnings(
        quality_warnings_from_preprocess(pre),
        quality_warnings_from_pose(pose_result),
    )

    phases = segment_chipping_phases(pose_result)
    features = extract_chipping_features(pose_result.keypoints, phases)
    scores = score_chipping(features)
    issues_raw = diagnose_chipping(features, phases, pose_result.keypoints)

    phase_scores_int = scores["phases"]
    weakest = min(CHIPPING_PHASE_ORDER, key=lambda p: phase_scores_int.get(p, 100))
    phase_scores = {
        p: PhaseScore(
            score=phase_scores_int.get(p, 0),
            label=CHIPPING_PHASE_LABELS[p],
            is_weakest=(p == weakest),
        )
        for p in CHIPPING_PHASE_ORDER
    }

    skeleton_url, thumb_url, skeleton_data_url, keyframe_urls = _produce_derived_assets(
        analysis_id=req.analysis_id,
        normalized_video_path=Path(pre.normalized_video_path),
        pose_result=pose_result,
        issues_raw=issues_raw,
        fallback_video_url=req.video_url,
    )

    issues = [
        IssueItem(
            type=it.type,
            name=it.name,
            severity=it.severity,
            description=it.description,
            key_frame_timestamp=it.key_frame_timestamp,
            key_frame_url=keyframe_urls.get(it.type),
        )
        for it in issues_raw
    ]

    duration_ms = int((time.perf_counter() - t0) * 1000)
    try:
        tmp = Path(pre.normalized_video_path)
        if tmp.exists() and tmp != Path(req.video_url):
            tmp.unlink()
    except Exception:  # pragma: no cover
        pass

    return AnalyzeResult(
        analysis_id=req.analysis_id,
        status="completed",
        analysis_mode="chipping",
        overall_score=scores["overall"],
        phase_scores=phase_scores,
        phase_timestamps=None,
        issues=issues,
        skeleton_video_url=skeleton_url,
        skeleton_data_url=skeleton_data_url,
        thumbnail_url=thumb_url,
        duration_ms=duration_ms,
        quality_warnings=quality_warnings,
    )
