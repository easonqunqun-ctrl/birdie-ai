"""P2-M7-11 W25 · 推杆 mode 真实分析编排。

调用链（与 full_swing ``run_real_analysis`` 同骨架，但走推杆专属 4 阶段/4 特征/评分/诊断）：

AnalyzeRequest(mode="putting")
  ├─ preprocess_video            （复用：下载 + 转码 + 质量门）
  ├─ estimate_poses              （复用：MediaPipe 33 点）
  ├─ segment_putting_phases      （W23：setup/backstroke/impact/follow）
  ├─ extract_putting_features    （W22：钟摆/头部/杆面/节奏）
  ├─ score_putting               （W24：overall + per-feature + per-phase）
  ├─ diagnose_putting            （W25：5 条 rule）
  └─ 组装 AnalyzeResult(analysis_mode="putting")

衍生产物（骨骼视频/缩略图/关键帧）复用 full_swing ``_produce_derived_assets``。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from app.pipeline.pose import estimate_poses, quality_warnings_from_pose
from app.pipeline.preprocess import preprocess_video, quality_warnings_from_preprocess
from app.pipeline.putting.constants import PUTTING_PHASE_LABELS, PUTTING_PHASE_ORDER
from app.pipeline.putting.diagnose import diagnose_putting
from app.pipeline.putting.features import extract_putting_features
from app.pipeline.putting.phases import segment_putting_phases
from app.pipeline.putting.scoring import score_putting
from app.pipeline.real_pipeline import _merge_quality_warnings, _produce_derived_assets
from app.schemas import AnalyzeRequest, AnalyzeResult, IssueItem, PhaseScore

log = logging.getLogger("ai_engine.putting.pipeline")


async def run_putting_analysis(req: AnalyzeRequest) -> AnalyzeResult:
    """推杆 mode 真实分析主入口（mode="putting" 时由 main.py 路由进入）。

    与 ``run_real_analysis`` 同为 ``async def`` 但内部同步；Celery 单任务模型下阻塞无碍。
    任何 ``PipelineError`` 往上抛，由 main.py 统一转 failed result。
    """
    t0 = time.perf_counter()
    log.info(
        "putting_analysis_start",
        extra={"analysis_id": req.analysis_id, "video_url": req.video_url},
    )

    # 1. 预处理 + 2. 姿态估计（复用 full_swing）
    pre = preprocess_video(req.video_url)
    pose_result = estimate_poses(pre.normalized_video_path)
    quality_warnings = _merge_quality_warnings(
        quality_warnings_from_preprocess(pre),
        quality_warnings_from_pose(pose_result),
    )

    # 3-6. 推杆专属：阶段 → 特征 → 评分 → 诊断
    phases = segment_putting_phases(pose_result)
    features = extract_putting_features(pose_result.keypoints, phases)
    scores = score_putting(features)
    issues_raw = diagnose_putting(
        features,
        phases,
        keypoints=pose_result.keypoints,
        valid_mask=pose_result.valid_mask,
    )

    # 7. 组装阶段分（取最弱阶段打徽章）
    phase_scores_int: dict[str, int] = scores["phases"]
    weakest = min(PUTTING_PHASE_ORDER, key=lambda p: phase_scores_int.get(p, 100))
    phase_scores: dict[str, PhaseScore] = {
        p: PhaseScore(
            score=phase_scores_int.get(p, 0),
            label=PUTTING_PHASE_LABELS[p],
            is_weakest=(p == weakest),
        )
        for p in PUTTING_PHASE_ORDER
    }

    # 8. 衍生产物（复用 full_swing；任一失败回落占位，不阻断主流程）
    derived = _produce_derived_assets(
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
            key_frame_url=derived.keyframe_urls.get(it.type),
        )
        for it in issues_raw
    ]

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log.info(
        "putting_analysis_done",
        extra={
            "analysis_id": req.analysis_id,
            "overall_score": scores["overall"],
            "weakest": weakest,
            "num_issues": len(issues),
            "duration_ms": duration_ms,
        },
    )

    # 清理预处理 tmp 视频
    try:
        tmp = Path(pre.normalized_video_path)
        if tmp.exists() and tmp != Path(req.video_url):
            tmp.unlink()
    except Exception:  # pragma: no cover
        pass

    engine_warnings = (
        [
            {
                "code": "skeleton_pending",
                "level": "info",
                "detail": "skeleton video rendering deferred",
            }
        ]
        if derived.skeleton_pending
        else []
    )
    return AnalyzeResult(
        analysis_id=req.analysis_id,
        status="completed",
        analysis_mode="putting",
        overall_score=scores["overall"],
        phase_scores=phase_scores,
        mode_feature_scores=scores["features"],
        phase_timestamps=None,  # 推杆 4 阶段与 full_swing PhaseTimestamps 6 段不同构，置空
        issues=issues,
        skeleton_video_url=derived.skeleton_video_url,
        skeleton_data_url=derived.skeleton_data_url,
        thumbnail_url=derived.thumbnail_url,
        duration_ms=duration_ms,
        quality_warnings=quality_warnings,
        skeleton_pending=derived.skeleton_pending,
        normalized_video_url=derived.normalized_video_url,
        engine_warnings=engine_warnings,
    )
