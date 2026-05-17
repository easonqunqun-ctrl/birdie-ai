"""挥杆分析业务逻辑：上传凭证签发、任务生命周期、列表查询。

T1 范围：创建的 SwingAnalysis 记录**停在 `pending`**，不触发 Celery；
T2 会在 `create_analysis` 末尾 `delay()` 到 worker，此处保留 hook 参数。
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    AnalysisDispatchError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ThirdPartyError,
    UploadObjectMissingError,
    UploadTokenInvalidError,
)
from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.models.training import TrainingPlan, TrainingTask
from app.models.user import User
from app.schemas.analysis import (
    STAGE_ETA_SECONDS,
    SWING_STAGE_TIMELINE,
    AnalysisListItem,
    AnalysisListQuery,
    AnalysisProgressPoint,
    AnalysisProgressResponse,
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
    estimate_swing_remaining_seconds,
    score_level,
)
from app.services import quota_service

log = logging.getLogger(__name__)

_KNOWN_ANALYSIS_STATUSES = frozenset({"pending", "processing", "completed", "failed"})
_KNOWN_ANALYSIS_STAGES = frozenset(name for name, _ in SWING_STAGE_TIMELINE)
_VALID_LIST_CAMERA_ANGLES = frozenset({"face_on", "down_the_line"})
_VALID_LIST_CLUB_TYPES = frozenset({
    "driver",
    "fairway_wood",
    "iron_3",
    "iron_4",
    "iron_5",
    "iron_6",
    "iron_7",
    "iron_8",
    "iron_9",
    "wedge",
    "putter",
    "unknown",
})


def normalize_list_camera_angle(
    camera_angle: str | None, *, analysis_id: str | None = None
) -> str:
    """列表项 DTO 与 schema `CameraAngle` 对齐；脏数据避免 ValidationError → HTTP 500."""
    if camera_angle in _VALID_LIST_CAMERA_ANGLES:
        return camera_angle
    log.warning(
        "invalid_swing_analysis_camera_angle_coerced",
        extra={"analysis_id": analysis_id, "raw": camera_angle},
    )
    return "face_on"


def normalize_list_club_type(club_type: str | None, *, analysis_id: str | None = None) -> str:
    """列表项与 schema `ClubType` 对齐。"""
    if club_type in _VALID_LIST_CLUB_TYPES:
        return club_type
    log.warning(
        "invalid_swing_analysis_club_type_coerced",
        extra={"analysis_id": analysis_id, "raw": club_type},
    )
    return "unknown"


def normalize_analysis_status(status: str | None, *, analysis_id: str | None = None) -> str:
    """防止 ORM 出现非法 status 时构造 Pydantic DTO 抛 ValidationError → 裸 HTTP 500."""
    if status in _KNOWN_ANALYSIS_STATUSES:
        return status
    log.warning(
        "invalid_swing_analysis_status_coerced",
        extra={"analysis_id": analysis_id, "raw_status": status},
    )
    return "pending"


def normalize_analysis_stage(stage: str | None, *, analysis_id: str | None = None) -> str | None:
    if stage is None:
        return None
    if stage in _KNOWN_ANALYSIS_STAGES:
        return stage
    log.warning(
        "invalid_swing_analysis_stage_cleared",
        extra={"analysis_id": analysis_id, "raw_stage": stage},
    )
    return None


def coerce_optional_db_int(val: Any, *, field: str, analysis_id: str | None = None) -> int | None:
    """PostgreSQL Numeric 等若以非 int 落入 ORM，`AnalysisListItem` 会 ValidationError→500."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        log.warning(
            "invalid_swing_numeric_coerced_none",
            extra={"analysis_id": analysis_id, "field": field, "raw": repr(val)},
        )
        return None


if TYPE_CHECKING:
    from app.integrations.minio import MinioStorageClient


UPLOAD_TOKEN_REDIS_KEY = "upload:token:{upload_id}"
UPLOAD_TOKEN_TTL_SECONDS = 3600
_UPLOAD_TOKEN_META_KEYS = frozenset(
    {"user_id", "bucket", "key", "file_size", "file_type", "duration"}
)


def _decode_upload_token_meta(raw: bytes | memoryview | str) -> dict[str, Any]:
    """解析 Redis 上传凭证 JSON；损坏或非预期结构时降级为凭证无效，避免裸 JSONDecodeError → HTTP 500."""
    try:
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        meta = json.loads(text)
        if not isinstance(meta, dict):
            raise ValueError("upload_token_meta_not_object")
        missing = _UPLOAD_TOKEN_META_KEYS - meta.keys()
        if missing:
            raise KeyError(next(iter(missing)))
        return meta
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, KeyError, TypeError):
        raise UploadTokenInvalidError()


def to_proxy_image_url(url: str | None) -> str | None:
    """把 MinIO 公网图片 URL 改写为 backend 同源代理 URL。

    解决：微信小程序在真机调试模式下，`<Image>` 组件对 9000 端口（与 API 不同源）
    的 HTTP 图片资源会静默拒绝（onError 触发但 errMsg 不明确），导致「问题诊断」
    卡片下的关键帧图全部空白。

    改写规则：
        in:  http://192.168.130.37:9000/xiaoniao-videos/keyframes/ana_xxx/casting.jpg
        out: http://192.168.130.37:8000/v1/assets/image/keyframes/ana_xxx/casting.jpg

    仅改写白名单前缀（keyframes/, thumbnails/）—— 与 backend `/v1/assets/image`
    路由的安全白名单一致。**视频**（uploads/, skeleton/）改写见 `to_proxy_video_url`。

    幂等：如果 URL 已经是代理路径或非 MinIO URL（如 CDN、未来 COS 公开域），
    原样返回；写库的旧值即使后端重启 API_PUBLIC_BASE_URL 变化也能正确改写。
    """
    if not url:
        return url
    public_endpoint = settings.effective_minio_public_endpoint.rstrip("/")
    bucket = settings.MINIO_BUCKET
    prefix = f"{public_endpoint}/{bucket}/"
    if not url.startswith(prefix):
        return url
    key = url[len(prefix):]
    if not (key.startswith("keyframes/") or key.startswith("thumbnails/")):
        # 视频等其他对象走 to_proxy_video_url（见下文）
        return url
    api_base = settings.effective_api_public_base_url.rstrip("/")
    return f"{api_base}/v1/assets/image/{key}"


def to_proxy_video_url(url: str | None) -> str | None:
    """把 MinIO 公网 / 容器内写入的 MP4 URL 改写为 backend 同源代理路径（支持 HTTP Range）。

    背景：微信小程序真机上 `<Video src=\"https://api…/minio/桶/…\">`
    常因「downloadFile / 视频播放入口」域名或路径策略与同源 API 不一致而黑屏（仅显示问号）。
    走 `{API_PUBLIC_BASE_URL}/v1/assets/video/{key}` 与 request 域名一致。

    兼容：AI 引擎写回的 `MINIO_PUBLIC_ENDPOINT` 若为 `http://minio:9000`（与 backend 回落后的
    effective 公网不一致）时，`skeleton_video_url` 会以内网形态入库；若不二次改写，
    报告页又因优先骨架视频而整块黑屏。**这里同时对 `MINIO_ENDPOINT`/`MINIO_PUBLIC_ENDPOINT`/`effective_*`
    三套前缀剥离 bucket/key。**
    """
    if not url:
        return url
    trimmed = url.strip()
    bucket = settings.MINIO_BUCKET

    prefixes: list[str] = []
    for base in (
        settings.effective_minio_public_endpoint,
        settings.MINIO_PUBLIC_ENDPOINT,
        settings.MINIO_ENDPOINT,
    ):
        b = str(base).strip().rstrip("/")
        if not b:
            continue
        prefixes.append(f"{b}/{bucket}/")

    # 次序保留 + 去重（effective 常与 MINIO_PUBLIC 相同）
    prefixes = list(dict.fromkeys(prefixes))

    api_base = settings.effective_api_public_base_url.rstrip("/")
    proxy_root = f"{api_base}/v1/assets/video/"
    if trimmed.startswith(proxy_root):
        return trimmed

    for prefix in prefixes:
        if trimmed.startswith(prefix):
            key = trimmed[len(prefix) :]
            if key.startswith(("uploads/", "skeleton/")):
                return f"{proxy_root}{key}"
            return trimmed

    return trimmed


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


async def finalize_analysis_dispatch_after_commit(
    *,
    redis: Redis,
    upload_id: str,
    analysis_id: str,
) -> None:
    """DB 事务已成功提交后调用：先入队 Celery，再作废上传凭证。

    入队失败时不删 Redis 凭证，以便用户（在仅因 broker 抖动失败时）可重试 `POST /analyses`；
    `create_analysis` 内对同 `video_url` 的 pending/processing 去重可避免双扣配额。
    """
    key = UPLOAD_TOKEN_REDIS_KEY.format(upload_id=upload_id)
    try:
        _dispatch_analysis_task(analysis_id)
    except Exception as exc:
        log.exception(
            "analysis_celery_dispatch_failed",
            extra={"analysis_id": analysis_id, "upload_id": upload_id},
        )
        raise AnalysisDispatchError(
            detail=str(exc) if settings.APP_DEBUG else None,
        ) from exc
    try:
        await redis.delete(key)
    except Exception as exc:
        log.warning(
            "upload_token_redis_delete_failed",
            extra={"upload_id": upload_id, "analysis_id": analysis_id, "err": str(exc)},
        )


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
# 3.1b POST /v1/analyses/uploads/{upload_id}/video（小程序同源兜底）
# ==================================================================
async def receive_upload_via_api(
    *,
    user: User,
    upload_id: str,
    file_body: bytes,
    redis: Redis,
    storage: MinioStorageClient,
) -> None:
    """经 API 网关接收视频字节并写入对象存储。

    微信小程序直连 MinIO 预签名 POST 在部分网关 / 开发者工具下易 502 或 timeout；
    此路径仅走已与 JWT 一致的 API 域名，由服务端写入 MinIO。
    """
    key_redis = UPLOAD_TOKEN_REDIS_KEY.format(upload_id=upload_id)
    raw = await redis.get(key_redis)
    if raw is None:
        raise UploadTokenInvalidError()
    meta = _decode_upload_token_meta(raw)
    if meta["user_id"] != user.id:
        raise UploadTokenInvalidError()

    n = len(file_body)
    if n == 0:
        raise BadRequestError(code=40005, message="上传文件为空")
    if n > settings.MAX_VIDEO_SIZE_BYTES:
        raise BadRequestError(
            code=40005,
            message=f"文件过大，请压缩后重试（上限 {settings.MAX_VIDEO_SIZE_BYTES // 1024 // 1024}MB）",
        )

    declared = int(meta["file_size"])
    # 不允许显著大于申报体积（防绕过）；小于申报允许（客户端 metadata 常有偏差）
    if n > declared + 512 * 1024:
        raise BadRequestError(
            code=40005,
            message="上传体积超过凭证申报，请返回上一页重新选择视频",
        )

    await asyncio.to_thread(
        storage.put_object_bytes,
        key=meta["key"],
        data=file_body,
        content_type=meta["file_type"],
    )

    # create_analysis 要求 head_object.size == meta.file_size：同步为实际上传字节数
    meta["file_size"] = n
    ttl_raw = await redis.ttl(key_redis)
    ex_sec = (
        UPLOAD_TOKEN_TTL_SECONDS if ttl_raw is None or ttl_raw < 1 else int(ttl_raw)
    )
    await redis.set(key_redis, json.dumps(meta), ex=ex_sec)


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
    """创建分析任务：落库 + 扣配额；Celery 调度见路由层 `finalize_analysis_dispatch_after_commit`。"""
    # 1) 取凭证上下文 & 归属校验
    raw = await redis.get(UPLOAD_TOKEN_REDIS_KEY.format(upload_id=payload.upload_id))
    if raw is None:
        raise UploadTokenInvalidError()
    meta = _decode_upload_token_meta(raw)
    if meta["user_id"] != user.id:
        # 不泄露他人 upload_id 是否存在，用 40011 统一响应
        raise UploadTokenInvalidError()

    # 2) 校验对象是否已真的传到 MinIO（head 非 404 的 S3 错误若冒泡会成为裸 50001）
    try:
        stat = storage.head_object(meta["key"])
    except Exception as exc:
        log.exception(
            "storage_head_object_failed",
            extra={"key": meta.get("key"), "upload_id": payload.upload_id},
        )
        raise ThirdPartyError(
            code=50203,
            http_status=502,
            message="存储服务暂时不可用，请稍后重试",
            detail=str(exc) if settings.APP_DEBUG else None,
        ) from exc
    if stat is None:
        raise UploadObjectMissingError()
    # 大小一致性检查：防止客户端篡改文件后上传（统一 int 比较，避免类型不一致误判）
    sz = stat.get("size")
    if sz is not None and int(sz) != int(meta["file_size"]):
        raise UploadObjectMissingError(message="上传文件大小与凭证声明不一致")

    video_url = storage.get_object_url(meta["key"])
    dup_stmt = (
        select(SwingAnalysis.id)
        .where(
            SwingAnalysis.user_id == user.id,
            SwingAnalysis.video_url == video_url,
            SwingAnalysis.status.in_(["pending", "processing"]),
            SwingAnalysis.deleted_at.is_(None),
        )
        .limit(1)
    )
    if (await db.execute(dup_stmt)).scalar_one_or_none():
        raise ConflictError(
            message="该视频已在分析队列中，请在分析记录或等待页查看进度",
        )

    # 3) 扣配额（可能抛 QuotaExceededError）
    await quota_service.consume_analysis_quota(db, user)

    # 4) 创建 SwingAnalysis 记录
    analysis_id = new_id("ana")
    is_member = user.membership_type != "free" and (
        user.membership_expires_at and user.membership_expires_at > datetime.now(UTC)
    )
    try:
        dur_val = float(meta["duration"])
    except (TypeError, ValueError):
        log.warning(
            "invalid_upload_token_duration",
            extra={"upload_id": payload.upload_id, "raw": meta.get("duration")},
        )
        dur_val = 0.0
    video_duration = Decimal(str(round(dur_val, 2)))

    analysis = SwingAnalysis(
        id=analysis_id,
        user_id=user.id,
        video_url=video_url,
        video_duration=video_duration,
        video_file_size=int(meta["file_size"]),
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
    await db.refresh(analysis)

    # 5) 凭证作废 + Celery 入队：须在路由层 `await db.commit()` **之后**调用，
    #    见 `finalize_analysis_dispatch_after_commit`（避免 worker 早于提交可见）

    # 6) 队列位置估算：当前 pending+processing 记录数（含本次，所以 -1）
    queue_count_stmt = select(func.count(SwingAnalysis.id)).where(
        SwingAnalysis.status.in_(["pending", "processing"]),
    )
    total_queued = (await db.execute(queue_count_stmt)).scalar_one()
    queue_position = max(0, int(total_queued) - 1)
    estimated_seconds = STAGE_ETA_SECONDS["pending"]

    created_ts = analysis.created_at
    if created_ts is None:
        log.warning(
            "swing_analysis_created_at_missing_after_refresh",
            extra={"analysis_id": analysis_id},
        )
        created_ts = datetime.now(UTC)

    return CreateAnalysisResponse(
        analysis_id=analysis_id,
        status="pending",
        queue_position=queue_position,
        estimated_seconds=estimated_seconds,
        created_at=created_ts,
    )


# ==================================================================
# 3.3 GET /v1/analyses/{id}/status
# ==================================================================
async def get_status(*, analysis_id: str, user: User, db: AsyncSession) -> AnalysisStatusResponse:
    analysis = await _load_owned(db, analysis_id, user)
    st_norm = normalize_analysis_status(analysis.status, analysis_id=analysis.id)
    sg_norm = normalize_analysis_stage(analysis.stage, analysis_id=analysis.id)
    eta = estimate_swing_remaining_seconds(
        status=st_norm,
        stage=sg_norm,
        stage_progress=analysis.stage_progress or 0,
    )
    error: AnalysisStatusError | None = None
    if analysis.status == "failed":
        error = AnalysisStatusError(
            code=analysis.error_code or 50001,
            message=analysis.error_message or "分析失败",
            quota_refunded=analysis.quota_refunded,
        )
    return AnalysisStatusResponse(
        analysis_id=analysis.id,
        status=st_norm,
        stage=sg_norm,
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
            key_frame_url=to_proxy_image_url(it.key_frame_url),
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
        status=normalize_analysis_status(analysis.status, analysis_id=analysis.id),
        camera_angle=analysis.camera_angle,  # type: ignore[arg-type]
        club_type=analysis.club_type,  # type: ignore[arg-type]
        video_url=to_proxy_video_url(analysis.video_url) or "",
        video_duration=float(analysis.video_duration) if analysis.video_duration else None,
        skeleton_video_url=to_proxy_video_url(analysis.skeleton_video_url),
        skeleton_data_url=analysis.skeleton_data_url,
        thumbnail_url=to_proxy_image_url(analysis.thumbnail_url),
        overall_score=analysis.overall_score,
        score_change=analysis.score_change,
        score_level=score_level(analysis.overall_score),
        phase_scores=phase_scores,
        phase_timestamps=phase_timestamps,
        issues=issues,
        recommendations=recs,
        share_card_url=to_proxy_image_url(analysis.share_card_url),
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
        SwingAnalysis.deleted_at.is_(None),
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
            camera_angle=normalize_list_camera_angle(r.camera_angle, analysis_id=r.id),  # type: ignore[arg-type]
            club_type=normalize_list_club_type(r.club_type, analysis_id=r.id),  # type: ignore[arg-type]
            overall_score=coerce_optional_db_int(
                r.overall_score, field="overall_score", analysis_id=r.id
            ),
            score_change=coerce_optional_db_int(
                r.score_change, field="score_change", analysis_id=r.id
            ),
            thumbnail_url=to_proxy_image_url(r.thumbnail_url),
            status=normalize_analysis_status(r.status, analysis_id=r.id),
            analyzed_at=r.analyzed_at,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return items, total


# ==================================================================
# MVP 进步曲线数据（§6.1）
# ==================================================================
async def get_user_analysis_progress(
    db: AsyncSession, user: User
) -> AnalysisProgressResponse:
    stmt = (
        select(SwingAnalysis)
        .where(
            SwingAnalysis.user_id == user.id,
            SwingAnalysis.is_sample.is_(False),
            SwingAnalysis.deleted_at.is_(None),
            SwingAnalysis.status == "completed",
            SwingAnalysis.overall_score.isnot(None),
        )
        .order_by(SwingAnalysis.analyzed_at.asc().nulls_last(), SwingAnalysis.created_at.asc())
        .limit(60)
    )
    rows = (await db.execute(stmt)).scalars().all()
    pts: list[AnalysisProgressPoint] = [
        AnalysisProgressPoint(
            analysis_id=r.id,
            analyzed_at=r.analyzed_at or r.created_at,
            overall_score=int(r.overall_score or 0),
        )
        for r in rows
    ]
    return AnalysisProgressResponse(points=pts)


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
    if analysis.deleted_at is not None:
        raise NotFoundError(code=40402, message="分析记录不存在")
    return analysis


async def _detach_training_analysis_refs(
    db: AsyncSession, *, analysis_id: str, user_id: str
) -> None:
    """软删分析前，清空训练计划/任务上指向该分析的 FK（DB 为 ON DELETE SET NULL，此处显式更新以立即生效）。"""
    await db.execute(
        update(TrainingPlan)
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source_analysis_id == analysis_id,
        )
        .values(source_analysis_id=None)
    )
    await db.execute(
        update(TrainingTask)
        .where(
            TrainingTask.user_id == user_id,
            TrainingTask.verification_analysis_id == analysis_id,
        )
        .values(verification_analysis_id=None)
    )


async def delete_analysis_for_user(
    *, analysis_id: str, user: User, db: AsyncSession
) -> None:
    """用户侧软删除：终态报告可删，队列中任务不可删；重复删除幂等。"""
    analysis = await db.get(SwingAnalysis, analysis_id)
    if analysis is None:
        raise NotFoundError(code=40402, message="分析记录不存在")
    if analysis.user_id != user.id:
        raise ForbiddenError(code=40301, message="无权访问该分析")
    if analysis.deleted_at is not None:
        return
    if analysis.is_sample:
        raise BadRequestError(code=40093, message="示例类型分析报告不可删除")
    if analysis.status in ("pending", "processing"):
        raise BadRequestError(code=40092, message="分析进行中，完成后才可删除")

    await _detach_training_analysis_refs(db, analysis_id=analysis_id, user_id=user.id)
    analysis.deleted_at = datetime.now(UTC)
    await db.flush()
