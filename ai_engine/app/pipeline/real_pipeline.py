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
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.config import settings
from app.pipeline.constants import PHASE_LABELS
from app.pipeline.diagnose import DiagnosedIssue, diagnose
from app.pipeline.features import extract_features
from app.pipeline.phases import PhaseSegmentResult
from app.pipeline.pose import PoseResult, estimate_poses, quality_warnings_from_pose
from app.pipeline.club_profiles import to_club_category
from app.pipeline.preprocess import quality_warnings_from_preprocess
from app.pipeline.preprocess_router import preprocess_for_pipeline
from app.pipeline.recommend import recommend_with_phase_fallback
from app.pipeline.scoring import score_all_phases, score_overall, weakest_phase
from app.pipeline.scoring_narrative import build_phase_highlights
from app.pipeline.visualize import (
    dump_pose_parquet,
    extract_issue_keyframes,
    make_artifacts_tmpdir,
    render_skeleton_video,
)
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResult,
    IssueItem,
    PhaseScore,
    PhaseTimestamps,
    SwingCandidateItem,
)
from app.storage import get_storage

# P2-W5：诊断函数协议。V1 默认 ``diagnose``；V2 灰度桶传 ``diagnose_v2``。
DiagnoseFn = Callable[[dict[str, float], PhaseSegmentResult], list[DiagnosedIssue]]


@dataclass(frozen=True)
class PipelineCtx:
    """P2-W7 ENG-B · 流水线中间态快照，供 V2 ``enrichment_fn`` 算 confidence / warnings.

    设计：用 frozen dataclass 而非裸 dict，免得 hook 误改导致 V1 行为漂移。
    扩展时直接加字段（向后兼容，旧 hook 只读自己关心的）。

    P2-W13-B：加 ``declared_camera_angle`` 让 V2 enrichment 能调
    ``camera_angle.attach_declared(...)`` 真生成 ``camera_angle_mismatch`` warning。
    向后兼容：默认 None；旧 hook（如 W7 _enrich_v2 在 W12 之前）不读不受影响。
    """

    pose_result: PoseResult
    phases: PhaseSegmentResult
    features: dict[str, float]
    quality_warnings: list[str]
    fps: float
    declared_camera_angle: str | None = None


# P2-W7 ENG-B：enrichment hook。V1 默认 None 不调用，保持行为冻结；
# V2 注入 ``_enrich_v2`` 在 result 组装完后填三层 confidence + engine_warnings。
EnrichmentFn = Callable[[AnalyzeResult, PipelineCtx], None]

log = logging.getLogger("ai_engine.real_pipeline")


async def run_real_analysis(
    req: AnalyzeRequest,
    *,
    diagnose_fn: DiagnoseFn | None = None,
    enrichment_fn: EnrichmentFn | None = None,
    club_aware_scoring: bool = False,
    use_preprocess_v2: bool = False,
) -> AnalyzeResult:
    """真实分析主入口（替换 mock_pipeline.run_mock_analysis）。

    该函数是 `async def` 以保持与 main.py 的签名兼容，但内部是同步 CPU/IO 密集工作；
    T5 如果需要可以包 `asyncio.to_thread`。MVP 期单进程单任务，阻塞 event loop 也没事
    （Celery worker 一次只处理一个分析）。

    P2-W5：``diagnose_fn`` 可注入。V1 默认走 ``diagnose``；
    ``real_pipeline_v2.run_real_analysis_v2`` 注入 ``diagnose_v2`` 走 YAML RuleEngine。

    P2-W7：``enrichment_fn`` 可注入。在 ``AnalyzeResult`` 组装完后被调用一次，
    收到 ``(result, ctx)``，可原地修改 result（如填 ``analysis_confidence``、
    ``feature_confidences``、``IssueItem.confidence`` 等）。V1 默认 None → 行为冻结。
    """
    diagnose_impl: DiagnoseFn = diagnose_fn or diagnose
    t0 = time.perf_counter()
    log.info(
        "real_analysis_start",
        extra={"analysis_id": req.analysis_id, "video_url": req.video_url},
    )

    # 1. 预处理（下载 + 转码 + 质量门）
    pre, preprocess_engine_warnings, preprocess_reader = preprocess_for_pipeline(
        req.video_url,
        use_v2=use_preprocess_v2,
    )
    fps = pre.fps
    log.info(
        "preprocess_done",
        extra={
            "frames": pre.num_frames,
            "fps": fps,
            "duration_sec": pre.duration_sec,
            "clarity": round(pre.clarity_score, 2),
            "preprocess_reader": preprocess_reader,
        },
    )

    # 2. 姿态估计 + 关键点时域降噪（减少单帧跳变污染特征）
    pose_result = estimate_poses(pre.normalized_video_path)
    from app.pipeline.pose_denoise import denoise_pose_result

    pose_result = denoise_pose_result(pose_result)
    from app.pipeline.pose_refine import refine_pose_result

    pose_result = refine_pose_result(pose_result)
    quality_warnings = _merge_quality_warnings(
        quality_warnings_from_preprocess(pre),
        quality_warnings_from_pose(pose_result),
    )
    log.info(
        "pose_done",
        extra={
            "valid_ratio": round(pose_result.valid_frame_ratio, 3),
            "num_frames": pose_result.num_frames,
        },
    )

    # 3. 阶段分割（P2-M7-13：full_swing 多挥识别 + 试挥过滤）
    swing_candidates_out: list[SwingCandidateItem] = []
    selected_idx: int | None = None
    ms_warning: dict | None = None
    from app.pipeline.multi_swing import (
        multi_swing_engine_warning,
        segment_phases_with_multi_swing,
    )

    phases, raw_candidates, selected_idx = segment_phases_with_multi_swing(
        pose_result,
        selected_swing_index=getattr(req, "selected_swing_index", None),
    )
    swing_candidates_out = [
        SwingCandidateItem(**c.to_dict(fps)) for c in raw_candidates
    ]
    ms_warning = multi_swing_engine_warning(raw_candidates, selected_idx, fps)

    # 4. 特征抽取 + 机位推断（须在 rotation_track 之前，B2 DTL 门控）
    features = extract_features(pose_result.keypoints, phases)

    from app.pipeline.camera_angle import infer_camera_angle_from_pose

    angle_result = infer_camera_angle_from_pose(
        pose_result, declared_raw=getattr(req, "camera_angle", None)
    )
    effective_camera_angle = angle_result.effective_angle

    rotation_track_meta: list = []
    from app.pipeline.rotation_track import apply_rotation_track

    features = apply_rotation_track(
        features,
        pose_result.keypoints,
        phases,
        visibility=pose_result.visibility,
        camera_angle=effective_camera_angle,  # type: ignore[arg-type]
        track_result_out=rotation_track_meta,
    )
    if rotation_track_meta and rotation_track_meta[0].quality_warnings:
        quality_warnings = _merge_quality_warnings(
            quality_warnings, rotation_track_meta[0].quality_warnings
        )

    club_category = (
        to_club_category(getattr(req, "club_type", None)) if club_aware_scoring else None
    )
    # P2-M7-R1：sanitize / 诊断全路径用 effective；计分仅 V2（club_aware）带机位 profile
    scoring_camera_angle = effective_camera_angle if club_aware_scoring else None
    from app.pipeline.feature_measurability import sanitize_features, scoring_quality_warnings
    from app.pipeline.scoring import collect_skipped_features_for_scoring

    features, sanitize_warnings = sanitize_features(
        features, camera_angle=effective_camera_angle  # type: ignore[arg-type]
    )
    quality_warnings = _merge_quality_warnings(quality_warnings, sanitize_warnings)
    if scoring_camera_angle is not None:
        from app.pipeline.feature_measurability import WARN_ANGLE_LIMITED_SCORING

        skipped = collect_skipped_features_for_scoring(
            features, camera_angle=scoring_camera_angle  # type: ignore[arg-type]
        )
        quality_warnings = _merge_quality_warnings(
            quality_warnings,
            scoring_quality_warnings(scoring_camera_angle, skipped),  # type: ignore[arg-type]
        )
        if sanitize_warnings and WARN_ANGLE_LIMITED_SCORING not in quality_warnings:
            quality_warnings = _merge_quality_warnings(
                quality_warnings, [WARN_ANGLE_LIMITED_SCORING]
            )

    # 5. 计分前特征置信度（V2：低置信维度不参与计分）
    feature_confidences_for_score = None
    if club_aware_scoring:
        from app.pipeline.feature_confidence_map import compute_feature_confidences

        feature_confidences_for_score = compute_feature_confidences(pose_result, phases)

    # 6. 评分（W22：``club_aware_scoring`` 仅由 V2 入口打开，搭 version_router 灰度爬坡；
    #    V1 默认 False → 两 profile 维度都 None → 阶段分用 V1 ideal、综合分用单套 PHASE_WEIGHTS，
    #    生产路径字节不变。打开时按 (机位, 球杆类别) 二维合成 per-feature ideal（阶段分）+
    #    相位权重（综合分）：ideal 优先级 category>angle>V1；权重 = V1+两维 delta 叠加。
    #    iron+无机位==V1；真实分析机位必填，故 V2 桶分数会带机位 delta（仅灰度桶）。)
    phase_scores_int = score_all_phases(
        features,
        club_category=club_category,
        camera_angle=scoring_camera_angle,
        feature_confidences=feature_confidences_for_score,
    )
    overall = score_overall(
        phase_scores_int,
        club_category=club_category,
        camera_angle=scoring_camera_angle,
        features=features,
        feature_confidences=feature_confidences_for_score,
    )
    weakest = weakest_phase(phase_scores_int)

    # 6. 诊断（V1 默认 ``diagnose``；V2 灰度桶可注入 ``diagnose_v2``）
    diagnose_guard_warnings: list[str] = []
    issues_raw = diagnose_impl(
        features,
        phases,
        camera_angle=effective_camera_angle,  # type: ignore[call-arg]
        guard_warnings_out=diagnose_guard_warnings,  # type: ignore[call-arg]
    )
    if diagnose_guard_warnings:
        quality_warnings = _merge_quality_warnings(
            quality_warnings, diagnose_guard_warnings
        )

    # 7. 推荐（无 issue 时按最弱阶段兜底）
    recommendations = recommend_with_phase_fallback(
        issues_raw,
        phase_scores=phase_scores_int,
        overall_score=overall,
        weakest_phase=weakest,
    )

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

    # 8. 可视化：3 类衍生产物 → MinIO（任一失败 → 占位 URL，主流程不受影响）
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
    log.info(
        "real_analysis_done",
        extra={
            "analysis_id": req.analysis_id,
            "overall_score": overall,
            "weakest": weakest,
            "num_issues": len(issues),
            "num_recommendations": len(recommendations),
            "skeleton_video_url": skeleton_url,
            "skeleton_data_url": skeleton_data_url,
            "duration_ms": duration_ms,
        },
    )

    # 清理：预处理产物 tmp 视频（避免 Celery worker 容器被临时文件塞满）。
    try:
        tmp = Path(pre.normalized_video_path)
        if tmp.exists() and tmp != Path(req.video_url):
            tmp.unlink()
    except Exception:  # pragma: no cover - 清理失败不影响主流程
        pass

    result = AnalyzeResult(
        analysis_id=req.analysis_id,
        status="completed",
        overall_score=overall,
        phase_scores=phase_scores,
        phase_timestamps=phase_timestamps,
        issues=issues,
        recommendations=recommendations,
        skeleton_video_url=skeleton_url,
        skeleton_data_url=skeleton_data_url,
        thumbnail_url=thumb_url,
        duration_ms=duration_ms,
        quality_warnings=quality_warnings,
        phase_highlights=build_phase_highlights(
            phase_scores_int, quality_warnings=quality_warnings
        ),
        swing_candidates=swing_candidates_out,
        selected_swing_index=selected_idx if raw_candidates else 0,
    )
    if preprocess_engine_warnings or ms_warning is not None:
        engine_w: list[dict] = list(preprocess_engine_warnings)
        if ms_warning is not None:
            engine_w.append(ms_warning)
        result.engine_warnings = engine_w

    # P2-W7 ENG-B：V2 通过 enrichment_fn 把三层 confidence + engine_warnings 注入 result；
    # V1 默认 enrichment_fn=None → 不调用 → analysis_confidence=1.0 / issues 无 confidence 字段（向后兼容）
    if enrichment_fn is not None:
        ctx = PipelineCtx(
            pose_result=pose_result,
            phases=phases,
            features=features,
            quality_warnings=quality_warnings,
            fps=fps,
            # P2-W13-B：把用户声明的机位透传给 V2 enrichment，让 attach_declared
            # 能算出 mismatch（用户声明 face_on 但 detected dtl 时 warning）
            declared_camera_angle=getattr(req, "camera_angle", None),
        )
        try:
            enrichment_fn(result, ctx)
        except Exception as exc:  # noqa: BLE001
            # enrichment 出错不影响主报告交付；记日志由调用方解决
            log.warning(
                "enrichment_fn_failed",
                extra={"analysis_id": req.analysis_id, "err": repr(exc)},
            )
        else:
            if club_aware_scoring:
                from app.pipeline.score_trust import calibrate_trusted_overall

                calibrated, trust_warnings = calibrate_trusted_overall(
                    result.overall_score or 0,
                    phase_scores_int,
                    feature_confidences=result.feature_confidences
                    or feature_confidences_for_score,
                    analysis_confidence=result.analysis_confidence or 1.0,
                    quality_warnings=quality_warnings,
                    camera_angle=scoring_camera_angle,
                )
                result.overall_score = calibrated
                if trust_warnings:
                    result.quality_warnings = _merge_quality_warnings(
                        result.quality_warnings or [], trust_warnings
                    )

    return result


def _merge_quality_warnings(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for code in group:
            c = str(code).strip()
            if not c or c in seen:
                continue
            seen.add(c)
            merged.append(c)
    return merged


# ============================================================
# T3：衍生产物生成 + 上传
# ============================================================


def _produce_derived_assets(
    *,
    analysis_id: str,
    normalized_video_path: Path,
    pose_result,
    issues_raw,
    fallback_video_url: str,
) -> tuple[str | None, str | None, str | None, dict[str, str]]:
    """生成三类产物 + 上传 MinIO，返回 4 个 URL/字典。

    任何一步失败：log warning，对应 URL 用占位（skeleton/thumb 用原视频后缀；
    parquet/keyframe 用 None）；从不抛错，保证主分析流程不被产物失败拖垮。

    Returns:
        (skeleton_video_url, thumbnail_url, skeleton_data_url, {issue_type: keyframe_url})
    """
    storage = get_storage()
    tmpdir = make_artifacts_tmpdir()
    skeleton_url: str | None = None
    thumb_url: str | None = None
    skeleton_data_url: str | None = None
    keyframe_urls: dict[str, str] = {}

    try:
        # ---------- A. 骨骼叠加视频 ----------
        skeleton_path = render_skeleton_video(
            normalized_video_path,
            pose_result,
            tmpdir / "skeleton.mp4",
        )
        if skeleton_path is not None:
            skeleton_key = f"{settings.DERIVED_SKELETON_PREFIX}/{analysis_id}.mp4"
            url = storage.put_file(skeleton_path, skeleton_key, content_type="video/mp4")
            skeleton_url = url or _placeholder_suffix(fallback_video_url, "_skeleton.mp4")
        else:
            skeleton_url = _placeholder_suffix(fallback_video_url, "_skeleton.mp4")

        # ---------- B. 缩略图：取视频前 1/6 处的一帧（接近 setup） ----------
        # 不叠加骨骼，避免封面图被绿色线条干扰
        from app.pipeline.visualize import extract_keyframe  # 局部 import 避免循环

        thumb_frame_idx = max(0, min(pose_result.num_frames // 6, pose_result.num_frames - 1))

        thumb_path = extract_keyframe(
            normalized_video_path,
            thumb_frame_idx,
            tmpdir / "thumb.jpg",
            pose_result=None,
            overlay_pose=False,
        )
        if thumb_path is not None:
            thumb_key = f"{settings.DERIVED_KEYFRAME_PREFIX}/{analysis_id}/thumb.jpg"
            url = storage.put_file(thumb_path, thumb_key, content_type="image/jpeg")
            thumb_url = url or _placeholder_suffix(fallback_video_url, "_thumb.jpg")
        else:
            thumb_url = _placeholder_suffix(fallback_video_url, "_thumb.jpg")

        # ---------- C. issue 关键帧图（叠骨骼，便于用户看出问题位置）----------
        keyframes_dir = tmpdir / "keyframes"
        local_kf_paths = extract_issue_keyframes(
            normalized_video_path, issues_raw, pose_result, keyframes_dir
        )
        for issue_type, local_path in local_kf_paths.items():
            kf_key = f"{settings.DERIVED_KEYFRAME_PREFIX}/{analysis_id}/{issue_type}.jpg"
            url = storage.put_file(local_path, kf_key, content_type="image/jpeg")
            if url is not None:
                keyframe_urls[issue_type] = url

        # ---------- D. parquet 骨骼时序 ----------
        parquet_path = dump_pose_parquet(pose_result, tmpdir / "pose.parquet")
        if parquet_path is not None:
            parquet_key = f"{settings.DERIVED_POSE_DATA_PREFIX}/{analysis_id}.parquet"
            skeleton_data_url = storage.put_file(
                parquet_path,
                parquet_key,
                content_type="application/vnd.apache.parquet",
            )
    finally:
        # tmpdir 整体清理；产物已经在 MinIO，本地副本不需要保留
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:  # pragma: no cover
            pass

    return skeleton_url, thumb_url, skeleton_data_url, keyframe_urls


def _placeholder_suffix(url: str, suffix: str) -> str:
    """把 .mp4 替换成 `_skeleton.mp4` / `_thumb.jpg`；保留 query 参数。"""
    if ".mp4" in url:
        return url.replace(".mp4", suffix, 1)
    if ".mov" in url:
        return url.replace(".mov", suffix, 1)
    return url + suffix
