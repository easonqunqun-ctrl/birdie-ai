"""挥杆分析业务逻辑：上传凭证签发、任务生命周期、列表查询。

T1 范围：创建的 SwingAnalysis 记录**停在 `pending`**，不触发 Celery；
T2 会在 `create_analysis` 末尾 `delay()` 到 worker，此处保留 hook 参数。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    UploadObjectMissingError,
    UploadTokenInvalidError,
)
from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.models.user import User
from app.schemas.analysis import (
    STAGE_ETA_SECONDS,
    AnalysisListItem,
    AnalysisListQuery,
    AnalysisReportResponse,
    AnalysisStatusError,
    AnalysisStatusResponse,
    CreateAnalysisRequest,
    CreateAnalysisResponse,
    IssueItem,
    PhaseScore,
    PhaseWindow,
    RecommendationItem,
    UploadTokenRequest,
    UploadTokenResponse,
    score_level,
)
from app.services import quota_service

if TYPE_CHECKING:
    from app.integrations.minio import MinioStorageClient


UPLOAD_TOKEN_REDIS_KEY = "upload:token:{upload_id}"
UPLOAD_TOKEN_TTL_SECONDS = 3600


def _dispatch_analysis_task(analysis_id: str) -> None:
    """派发挥杆分析 Celery 任务。

    单独抽成顶层函数有两个好处：
    1. 测试中通过 `monkeypatch.setattr(analysis_service, '_dispatch_analysis_task', ...)` 拦截，
       不依赖 celery broker 即可跑完 `POST /analyses` 链路。
    2. 生产环境中 delay() 调用失败（broker 短暂不可达）时，这里是唯一的 fault 位置，
       将来可以挂重试 / 告警。
    """
    from app.tasks.analysis_tasks import run_swing_analysis

    run_swing_analysis.delay(analysis_id)


# ==================================================================
# 3.1 POST /v1/analyses/upload-token
# ==================================================================
async def create_upload_token(
    *,
    user: User,
    payload: UploadTokenRequest,
    db: AsyncSession,
    redis: Redis,
    storage: MinioStorageClient,
) -> UploadTokenResponse:
    """签发一次性上传凭证。

    - 业务规则：文件规格预校验（大小/时长/格式）+ 配额预检（不扣减）。
    - 存储规则：`key = uploads/YYYY/MM/DD/{user_id}/{upload_id}{.ext}`，按日期分桶便于清理。
    """
    # 1) 规格校验（与 MVP §4.1 对齐）
    from app.core.exceptions import BadRequestError

    if payload.file_size > settings.MAX_VIDEO_SIZE_BYTES:
        raise BadRequestError(
            code=40005,
            message=f"视频文件过大，请压缩后重试（上限 {settings.MAX_VIDEO_SIZE_BYTES // 1024 // 1024}MB）",
        )
    if payload.duration < settings.MIN_VIDEO_DURATION_SECONDS:
        raise BadRequestError(code=40004, message="视频时长不足 3 秒，请拍摄完整挥杆过程")
    if payload.duration > settings.MAX_VIDEO_DURATION_SECONDS:
        raise BadRequestError(code=40004, message="视频超过 30 秒，请裁剪后重试")

    # 2) 配额预检（不扣减）
    await quota_service.check_analysis_quota(db, user)

    # 3) 分配 upload_id 与对象 key
    upload_id = new_id("upl")
    ext = ".mov" if payload.file_type == "video/quicktime" else ".mp4"
    now = datetime.now(UTC)
    key = f"uploads/{now.year:04d}/{now.month:02d}/{now.day:02d}/{user.id}/{upload_id}{ext}"

    # 4) 签 POST policy（expires 1h；max_size 100MB）
    url, fields, expires_at = storage.presign_post_policy(
        key=key,
        content_type=payload.file_type,
        max_size=settings.MAX_VIDEO_SIZE_BYTES,
        expires_in_seconds=UPLOAD_TOKEN_TTL_SECONDS,
    )

    # 5) Redis 登记凭证上下文（T2 消费时核验 user_id、从 key 取原始视频）
    await redis.set(
        UPLOAD_TOKEN_REDIS_KEY.format(upload_id=upload_id),
        json.dumps(
            {
                "user_id": user.id,
                "bucket": storage.bucket,
                "key": key,
                "file_size": payload.file_size,
                "file_type": payload.file_type,
                "duration": payload.duration,
                "issued_at": now.isoformat(),
            }
        ),
        ex=UPLOAD_TOKEN_TTL_SECONDS,
    )

    return UploadTokenResponse(
        upload_id=upload_id,
        upload_url=url,
        bucket=storage.bucket,
        key=key,
        fields=fields,
        expires_at=expires_at,
        max_file_size=settings.MAX_VIDEO_SIZE_BYTES,
    )


# ==================================================================
# 3.2 POST /v1/analyses
# ==================================================================
async def create_analysis(
    *,
    user: User,
    payload: CreateAnalysisRequest,
    db: AsyncSession,
    redis: Redis,
    storage: MinioStorageClient,
) -> CreateAnalysisResponse:
    """创建分析任务。T1 只建记录 + 扣配额，不触发 Celery（T2 补 .delay() 调度）。"""
    # 1) 取凭证上下文 & 归属校验
    raw = await redis.get(UPLOAD_TOKEN_REDIS_KEY.format(upload_id=payload.upload_id))
    if raw is None:
        raise UploadTokenInvalidError()
    meta = json.loads(raw)
    if meta["user_id"] != user.id:
        # 不泄露他人 upload_id 是否存在，用 40011 统一响应
        raise UploadTokenInvalidError()

    # 2) 校验对象是否已真的传到 MinIO
    stat = storage.head_object(meta["key"])
    if stat is None:
        raise UploadObjectMissingError()
    # 大小一致性检查：防止客户端篡改文件后上传
    if stat.get("size") and stat["size"] != meta["file_size"]:
        raise UploadObjectMissingError(message="上传文件大小与凭证声明不一致")

    # 3) 扣配额（可能抛 QuotaExceededError）
    await quota_service.consume_analysis_quota(db, user)

    # 4) 创建 SwingAnalysis 记录
    analysis_id = new_id("ana")
    video_url = storage.get_object_url(meta["key"])
    is_member = user.membership_type != "free" and (
        user.membership_expires_at and user.membership_expires_at > datetime.now(UTC)
    )
    analysis = SwingAnalysis(
        id=analysis_id,
        user_id=user.id,
        video_url=video_url,
        video_duration=Decimal(str(round(meta["duration"], 2))),
        video_file_size=meta["file_size"],
        camera_angle=payload.camera_angle,
        club_type=payload.club_type,
        status="pending",
        stage=None,
        stage_progress=0,
        quota_refunded=False,
        priority="priority" if is_member else "standard",
        is_sample=False,
    )
    db.add(analysis)
    await db.flush()

    # 5) 凭证一次性：用过即删
    await redis.delete(UPLOAD_TOKEN_REDIS_KEY.format(upload_id=payload.upload_id))

    # 6) 队列位置估算：当前 pending+processing 记录数（含本次，所以 -1）
    queue_count_stmt = select(func.count(SwingAnalysis.id)).where(
        SwingAnalysis.status.in_(["pending", "processing"]),
    )
    total_queued = (await db.execute(queue_count_stmt)).scalar_one()
    queue_position = max(0, int(total_queued) - 1)
    estimated_seconds = STAGE_ETA_SECONDS["pending"]

    # 7) 触发 Celery 任务（T2）。`_dispatch_analysis_task` 独立抽出以便测试 monkeypatch。
    _dispatch_analysis_task(analysis_id)

    return CreateAnalysisResponse(
        analysis_id=analysis_id,
        status="pending",
        queue_position=queue_position,
        estimated_seconds=estimated_seconds,
        created_at=analysis.created_at,
    )


# ==================================================================
# 3.3 GET /v1/analyses/{id}/status
# ==================================================================
async def get_status(*, analysis_id: str, user: User, db: AsyncSession) -> AnalysisStatusResponse:
    analysis = await _load_owned(db, analysis_id, user)
    eta = STAGE_ETA_SECONDS.get(analysis.stage or analysis.status, 0)
    error: AnalysisStatusError | None = None
    if analysis.status == "failed":
        error = AnalysisStatusError(
            code=analysis.error_code or 50001,
            message=analysis.error_message or "分析失败",
            quota_refunded=analysis.quota_refunded,
        )
    return AnalysisStatusResponse(
        analysis_id=analysis.id,
        status=analysis.status,
        stage=analysis.stage,
        stage_progress=analysis.stage_progress,
        estimated_remaining_seconds=eta,
        error=error,
    )


# ==================================================================
# 3.4 GET /v1/analyses/{id}
# ==================================================================
async def get_report(*, analysis_id: str, user: User, db: AsyncSession) -> AnalysisReportResponse:
    from app.core.exceptions import ConflictError

    analysis = await _load_owned(db, analysis_id, user, load_children=True)
    if analysis.status != "completed":
        raise ConflictError(
            code=40904,
            message=f"分析尚未完成（当前状态 {analysis.status}），请先查询 /status 接口",
        )

    phase_scores = None
    if analysis.phase_scores:
        phase_scores = {
            k: PhaseScore(**v) if isinstance(v, dict) else v
            for k, v in analysis.phase_scores.items()
        }
    phase_timestamps = None
    if analysis.phase_timestamps:
        phase_timestamps = {
            k: PhaseWindow(**v) if isinstance(v, dict) else v
            for k, v in analysis.phase_timestamps.items()
        }

    issues = [
        IssueItem(
            type=it.issue_type,
            name=it.name,
            severity=it.severity,  # type: ignore[arg-type]
            description=it.description,
            key_frame_url=it.key_frame_url,
            key_frame_timestamp=float(it.key_frame_timestamp)
            if it.key_frame_timestamp is not None
            else None,
        )
        for it in sorted(analysis.issues, key=lambda x: x.sort_order)
    ]
    recs = [
        RecommendationItem(
            drill_id=r.drill_id,
            target_issue=r.target_issue,
            sort_order=r.sort_order,
        )
        for r in sorted(analysis.recommendations, key=lambda x: x.sort_order)
    ]

    return AnalysisReportResponse(
        id=analysis.id,
        user_id=analysis.user_id,
        status=analysis.status,  # type: ignore[arg-type]
        camera_angle=analysis.camera_angle,  # type: ignore[arg-type]
        club_type=analysis.club_type,  # type: ignore[arg-type]
        video_url=analysis.video_url,
        video_duration=float(analysis.video_duration) if analysis.video_duration else None,
        skeleton_video_url=analysis.skeleton_video_url,
        skeleton_data_url=analysis.skeleton_data_url,
        thumbnail_url=analysis.thumbnail_url,
        overall_score=analysis.overall_score,
        score_change=analysis.score_change,
        score_level=score_level(analysis.overall_score),
        phase_scores=phase_scores,
        phase_timestamps=phase_timestamps,
        issues=issues,
        recommendations=recs,
        share_card_url=analysis.share_card_url,
        analyzed_at=analysis.analyzed_at,
        created_at=analysis.created_at,
    )


# ==================================================================
# 3.5 GET /v1/analyses
# ==================================================================
async def list_analyses(
    *, user: User, query: AnalysisListQuery, db: AsyncSession
) -> tuple[list[AnalysisListItem], int]:
    conds = [
        SwingAnalysis.user_id == user.id,
        SwingAnalysis.is_sample.is_(False),
    ]
    if query.club_type:
        conds.append(SwingAnalysis.club_type == query.club_type)
    if query.date_from:
        conds.append(SwingAnalysis.created_at >= query.date_from)
    if query.date_to:
        conds.append(SwingAnalysis.created_at <= query.date_to)

    total_stmt = select(func.count(SwingAnalysis.id)).where(and_(*conds))
    total = int((await db.execute(total_stmt)).scalar_one())

    offset = (query.page - 1) * query.page_size
    rows_stmt = (
        select(SwingAnalysis)
        .where(and_(*conds))
        .order_by(SwingAnalysis.created_at.desc())
        .offset(offset)
        .limit(query.page_size)
    )
    rows = (await db.execute(rows_stmt)).scalars().all()
    items = [
        AnalysisListItem(
            id=r.id,
            camera_angle=r.camera_angle,  # type: ignore[arg-type]
            club_type=r.club_type,  # type: ignore[arg-type]
            overall_score=r.overall_score,
            score_change=r.score_change,
            thumbnail_url=r.thumbnail_url,
            status=r.status,  # type: ignore[arg-type]
            analyzed_at=r.analyzed_at,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return items, total


# ==================================================================
# 内部工具
# ==================================================================
async def _load_owned(
    db: AsyncSession,
    analysis_id: str,
    user: User,
    *,
    load_children: bool = False,
) -> SwingAnalysis:
    from sqlalchemy.orm import selectinload

    stmt = select(SwingAnalysis).where(SwingAnalysis.id == analysis_id)
    if load_children:
        stmt = stmt.options(
            selectinload(SwingAnalysis.issues),
            selectinload(SwingAnalysis.recommendations),
        )
    analysis = (await db.execute(stmt)).scalar_one_or_none()
    if analysis is None:
        raise NotFoundError(code=40402, message="分析记录不存在")
    if analysis.user_id != user.id:
        # 不区分 404/403，统一用 403（不泄露他人 id 的存在性）
        raise ForbiddenError(code=40301, message="无权访问该分析")
    return analysis
