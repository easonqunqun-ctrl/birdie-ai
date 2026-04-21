"""W6-T2：串联六阶段的真实分析管线。

调用链
------
AnalyzeRequest
  ├─ preprocess (T1)：下载视频 → ffmpeg 转码 → 质量门
  ├─ estimate_poses (T1)：MediaPipe 33 点
  ├─ segment_phases (T2)：六阶段
  ├─ extract_features (T2)：15 个特征
  ├─ scoring        (T2)：feature/phase/overall 分 + weakest
  ├─ diagnose       (T2)：15 条 rule → issues
  ├─ recommend      (T2)：issue → drill，最多 3 条
  └─ 组装 AnalyzeResult（skeleton_*_url 占位，T3 接 MinIO）

错误处理
--------
任何 PipelineError 往上抛；main.py 的 analyze 路由统一捕获转成 `AnalyzeResult(status="failed",
error_code=..., error_message=...)`。

性能预算（docs/14 §5）
---------------------
- 10s @30fps 视频：E2E < 30s（含下载），其中 pose 3-8s，phases/features/scoring/diagnose
  总和 < 2s（都在 O(F) 或 O(F×几个 landmarks)）
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from app.pipeline.diagnose import diagnose
from app.pipeline.features import extract_features
from app.pipeline.phases import segment_phases
from app.pipeline.pose import estimate_poses
from app.pipeline.preprocess import preprocess_video
from app.pipeline.recommend import recommend
from app.pipeline.scoring import score_all_phases, score_overall, weakest_phase
from app.pipeline.constants import PHASE_LABELS
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResult,
    IssueItem,
    PhaseScore,
    PhaseTimestamps,
)

log = logging.getLogger("ai_engine.real_pipeline")


async def run_real_analysis(req: AnalyzeRequest) -> AnalyzeResult:
    """真实分析主入口（替换 mock_pipeline.run_mock_analysis）。

    该函数是 `async def` 以保持与 main.py 的签名兼容，但内部是同步 CPU/IO 密集工作；
    T5 如果需要可以包 `asyncio.to_thread`。MVP 期单进程单任务，阻塞 event loop 也没事
    （Celery worker 一次只处理一个分析）。
    """
    t0 = time.perf_counter()
    log.info(
        "real_analysis_start",
        extra={"analysis_id": req.analysis_id, "video_url": req.video_url},
    )

    # 1. 预处理（下载 + 转码 + 质量门）
    pre = preprocess_video(req.video_url)
    fps = pre.fps
    log.info(
        "preprocess_done",
        extra={
            "frames": pre.frame_count,
            "fps": fps,
            "duration_sec": pre.duration_sec,
            "clarity": round(pre.clarity_score, 2),
        },
    )

    # 2. 姿态估计
    pose_result = estimate_poses(pre.normalized_path)
    log.info(
        "pose_done",
        extra={
            "valid_ratio": round(pose_result.valid_frame_ratio, 3),
            "num_frames": pose_result.num_frames,
        },
    )

    # 3. 阶段分割
    phases = segment_phases(pose_result)

    # 4. 特征抽取
    features = extract_features(pose_result.keypoints, phases)

    # 5. 评分
    phase_scores_int = score_all_phases(features)
    overall = score_overall(phase_scores_int)
    weakest = weakest_phase(phase_scores_int)

    # 6. 诊断
    issues_raw = diagnose(features, phases)

    # 7. 推荐
    recommendations = recommend(issues_raw)

    # 8. 组装 schema
    phase_scores: dict[str, PhaseScore] = {
        p: PhaseScore(score=s, label=PHASE_LABELS[p], is_weakest=(p == weakest))
        for p, s in phase_scores_int.items()
    }

    phase_timestamps = PhaseTimestamps(
        setup={
            "start": phases.phases["setup"].start_time(fps),
            "end": phases.phases["setup"].end_time(fps),
        },
        backswing={
            "start": phases.phases["backswing"].start_time(fps),
            "end": phases.phases["backswing"].end_time(fps),
        },
        top={
            "start": phases.phases["top"].start_time(fps),
            "end": phases.phases["top"].end_time(fps),
        },
        downswing={
            "start": phases.phases["downswing"].start_time(fps),
            "end": phases.phases["downswing"].end_time(fps),
        },
        impact={
            "start": phases.phases["impact"].start_time(fps),
            "end": phases.phases["impact"].end_time(fps),
        },
        follow_through={
            "start": phases.phases["follow_through"].start_time(fps),
            "end": phases.phases["follow_through"].end_time(fps),
        },
    )

    issues = [
        IssueItem(
            type=it.type,
            name=it.name,
            severity=it.severity,
            description=it.description,
            key_frame_timestamp=it.key_frame_timestamp,
        )
        for it in issues_raw
    ]

    # skeleton_video_url / thumbnail_url：T3 才接 MinIO。MVP 阶段继续沿用 mock 的
    # "把原 URL 后缀改一下"占位模式，后端看到这个就能先把 analyzing 流程打通。
    skeleton_url = _placeholder_suffix(req.video_url, "_skeleton.mp4")
    thumb_url = _placeholder_suffix(req.video_url, "_thumb.jpg")

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log.info(
        "real_analysis_done",
        extra={
            "analysis_id": req.analysis_id,
            "overall_score": overall,
            "weakest": weakest,
            "num_issues": len(issues),
            "num_recommendations": len(recommendations),
            "duration_ms": duration_ms,
        },
    )

    # 清理：预处理产物 tmp 视频（避免 Celery worker 容器被临时文件塞满）。
    try:
        tmp = Path(pre.normalized_path)
        if tmp.exists() and tmp != Path(req.video_url):
            tmp.unlink()
    except Exception:  # pragma: no cover - 清理失败不影响主流程
        pass

    return AnalyzeResult(
        analysis_id=req.analysis_id,
        status="completed",
        overall_score=overall,
        phase_scores=phase_scores,
        phase_timestamps=phase_timestamps,
        issues=issues,
        recommendations=recommendations,
        skeleton_video_url=skeleton_url,
        thumbnail_url=thumb_url,
        duration_ms=duration_ms,
    )


def _placeholder_suffix(url: str, suffix: str) -> str:
    """把 .mp4 替换成 `_skeleton.mp4` / `_thumb.jpg`；保留 query 参数。"""
    if ".mp4" in url:
        return url.replace(".mp4", suffix, 1)
    if ".mov" in url:
        return url.replace(".mov", suffix, 1)
    return url + suffix
