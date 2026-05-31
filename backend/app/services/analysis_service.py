"""挥杆分析业务逻辑：上传凭证签发、任务生命周期、列表查询。

T1 范围：创建的 SwingAnalysis 记录**停在 `pending`**，不触发 Celery；
T2 会在 `create_analysis` 末尾 `delay()` 到 worker，此处保留 hook 参数。
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants.chipping import (
    CHIPPING_FEATURE_LABELS,
    CHIPPING_FEATURE_ORDER,
    CHIPPING_FEATURE_PRIMARY_PHASE,
)
from app.constants.putting import (
    PUTTING_FEATURE_LABELS,
    PUTTING_FEATURE_ORDER,
    PUTTING_FEATURE_PRIMARY_PHASE,
)
from app.core.exceptions import (
    AIEngineError,
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
    DetectSwingsResponse,
    IssueItem,
    PhaseScore,
    PhaseWindow,
    RecommendationItem,
    ScorePercentileResponse,
    SwingCandidateItem,
    UploadTokenRequest,
    UploadTokenResponse,
    estimate_swing_remaining_seconds,
    score_level,
)
from app.services import quota_service
from app.services.scoring_narrative import build_phase_highlights

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


def _coerce_list_confidence(val: Any) -> float | None:
    """P2-W11：列表卡片 V2 可信度 sanitize。

    历史 V1 报告 / 异常落库的 NaN / Inf / 越界值都 → None，前端就不渲染小标签
    （不会让 Pydantic 在边界 validation 抛 500）。
    """
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


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

    仅改写白名单前缀（keyframes/, thumbnails/, share/wxa/）—— 与 backend `/v1/assets/image`
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
    if not (
        key.startswith("keyframes/")
        or key.startswith("thumbnails/")
        or key.startswith("share/wxa/")
    ):
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
            if key.startswith(("uploads/", "skeleton/", "samples/", "pro-clips/")):
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
    request_role: str | None = None,
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
        raise BadRequestError(code=40004, message="视频时长不足 2 秒，请拍摄完整挥杆过程")
    if payload.duration > settings.MAX_VIDEO_DURATION_SECONDS:
        raise BadRequestError(code=40004, message="视频超过 30 秒，请裁剪后重试")

    # 2) 配额预检（不扣减）
    await quota_service.check_analysis_quota(
        db, user, request_role=request_role, redis=redis
    )

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
# 3.1c POST /v1/analyses/uploads/{upload_id}/detect-swings
# ==================================================================
async def detect_swings_for_upload(
    *,
    user: User,
    upload_id: str,
    redis: Redis,
    storage: MinioStorageClient,
) -> DetectSwingsResponse:
    """上传完成后、创建任务前探测多挥候选（不扣配额）。"""
    from app.integrations.ai_engine import get_ai_engine

    raw = await redis.get(UPLOAD_TOKEN_REDIS_KEY.format(upload_id=upload_id))
    if raw is None:
        raise UploadTokenInvalidError()
    meta = _decode_upload_token_meta(raw)
    if meta["user_id"] != user.id:
        raise UploadTokenInvalidError()

    try:
        stat = storage.head_object(meta["key"])
    except Exception as exc:
        log.exception(
            "storage_head_object_failed",
            extra={"key": meta.get("key"), "upload_id": upload_id},
        )
        raise ThirdPartyError(
            code=50203,
            http_status=502,
            message="存储服务暂时不可用，请稍后重试",
            detail=str(exc) if settings.APP_DEBUG else None,
        ) from exc
    if stat is None:
        raise UploadObjectMissingError()

    video_url = storage.get_object_url(meta["key"])
    client = get_ai_engine()
    try:
        result = await client.detect_swings(
            analysis_id=upload_id,
            video_url=video_url,
        )
    except Exception as exc:
        log.exception(
            "ai_engine_detect_swings_call_failed",
            extra={"upload_id": upload_id},
        )
        raise AIEngineError(
            message="挥杆探测服务暂时不可用，请稍后重试",
            detail=str(exc) if settings.APP_DEBUG else None,
        ) from exc

    if result.get("status") == "failed":
        code = int(result.get("error_code") or 50101)
        msg = str(result.get("error_message") or "挥杆探测失败")
        if 50101 <= code <= 50123:
            raise BadRequestError(code=code, message=msg)
        raise AIEngineError(code=code, message=msg)

    return DetectSwingsResponse(
        upload_id=upload_id,
        swing_candidates=_map_swing_candidates(result.get("swing_candidates") or []),
        default_selected_index=int(result.get("default_selected_index") or 0),
        suggested_camera_angle=result.get("suggested_camera_angle"),
        detected_camera_angle=result.get("detected_camera_angle"),
        camera_angle_confidence=result.get("camera_angle_confidence"),
    )


def _map_swing_candidates(raw_list: list) -> list[SwingCandidateItem]:
    """透传 ai_engine 候选并改写 preview_frame_url 为同源代理。"""
    out: list[SwingCandidateItem] = []
    for item in raw_list:
        data = dict(item) if isinstance(item, dict) else item.model_dump()
        preview = data.get("preview_frame_url")
        if preview:
            data["preview_frame_url"] = to_proxy_image_url(preview)
        out.append(SwingCandidateItem(**data))
    return out


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
    request_role: str | None = None,
) -> CreateAnalysisResponse:
    """创建分析任务：落库 + 扣配额；Celery 调度见路由层 `finalize_analysis_dispatch_after_commit`。"""
    mode = payload.mode or "full_swing"
    if mode == "putting" and not settings.PHASE2_PUTTING_MODE_ENABLED:
        raise BadRequestError(message="推杆模式尚未开放")
    if mode == "chipping" and not settings.PHASE2_CHIPPING_MODE_ENABLED:
        raise BadRequestError(message="切杆模式尚未开放")

    target_yardage: int | None = None
    if payload.target_yardage is not None:
        if not settings.PHASE2_YARDAGE_BOOK_ENABLED:
            raise BadRequestError(message="目标码数尚未开放")
        if mode != "full_swing":
            raise BadRequestError(message="仅全挥杆分析可填写目标码数")
        target_yardage = payload.target_yardage

    selected_swing_index: int | None = None
    if payload.selected_swing_index is not None:
        if mode != "full_swing":
            raise BadRequestError(message="仅全挥杆分析可指定挥杆段索引")
        selected_swing_index = payload.selected_swing_index

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
    await quota_service.consume_analysis_quota(
        db, user, request_role=request_role, redis=redis
    )

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
        analysis_mode=mode,
        target_yardage=target_yardage,
        selected_swing_index=selected_swing_index,
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
def _build_putting_features(analysis: SwingAnalysis) -> dict[str, PhaseScore] | None:
    """推杆 mode 专属 4 维度；优先 mode_feature_scores，缺失时从 phase_scores 兜底。"""
    if getattr(analysis, "analysis_mode", "full_swing") != "putting":
        return None

    raw = getattr(analysis, "mode_feature_scores", None)
    if isinstance(raw, dict) and raw:
        out: dict[str, PhaseScore] = {}
        for name in PUTTING_FEATURE_ORDER:
            val = raw.get(name)
            if isinstance(val, int):
                out[name] = PhaseScore(
                    score=val,
                    label=PUTTING_FEATURE_LABELS.get(name, name),
                )
        if out:
            weakest = min(out, key=lambda k: out[k].score)
            for k in out:
                out[k] = out[k].model_copy(update={"is_weakest": k == weakest})
            return out

    phase_scores = analysis.phase_scores if isinstance(analysis.phase_scores, dict) else {}
    if not phase_scores:
        return None

    out = {}
    for name in PUTTING_FEATURE_ORDER:
        phase_key = PUTTING_FEATURE_PRIMARY_PHASE.get(name, "impact")
        ps = phase_scores.get(phase_key)
        score_val = ps.get("score") if isinstance(ps, dict) else None
        if isinstance(score_val, int):
            out[name] = PhaseScore(
                score=score_val,
                label=PUTTING_FEATURE_LABELS.get(name, name),
            )
    if not out:
        return None
    weakest = min(out, key=lambda k: out[k].score)
    for k in out:
        out[k] = out[k].model_copy(update={"is_weakest": k == weakest})
    return out


def _build_chipping_features(analysis: SwingAnalysis) -> dict[str, PhaseScore] | None:
    """切杆 mode 专属 3 维度；优先 mode_feature_scores，缺失时从 phase_scores 兜底。"""
    if getattr(analysis, "analysis_mode", "full_swing") != "chipping":
        return None

    raw = getattr(analysis, "mode_feature_scores", None)
    if isinstance(raw, dict) and raw:
        out: dict[str, PhaseScore] = {}
        for name in CHIPPING_FEATURE_ORDER:
            val = raw.get(name)
            if isinstance(val, int):
                out[name] = PhaseScore(
                    score=val,
                    label=CHIPPING_FEATURE_LABELS.get(name, name),
                )
        if out:
            weakest = min(out, key=lambda k: out[k].score)
            for k in out:
                out[k] = out[k].model_copy(update={"is_weakest": k == weakest})
            return out

    phase_scores = analysis.phase_scores if isinstance(analysis.phase_scores, dict) else {}
    if not phase_scores:
        return None

    out = {}
    for name in CHIPPING_FEATURE_ORDER:
        phase_key = CHIPPING_FEATURE_PRIMARY_PHASE.get(name, "impact")
        ps = phase_scores.get(phase_key)
        score_val = ps.get("score") if isinstance(ps, dict) else None
        if isinstance(score_val, int):
            out[name] = PhaseScore(
                score=score_val,
                label=CHIPPING_FEATURE_LABELS.get(name, name),
            )
    if not out:
        return None
    weakest = min(out, key=lambda k: out[k].score)
    for k in out:
        out[k] = out[k].model_copy(update={"is_weakest": k == weakest})
    return out


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
            # P2-W10：透传 V2 引擎诊断置信度，让客户端区分 confirmed/leaning/hidden
            confidence=float(it.confidence) if it.confidence is not None else None,
            confidence_tier=(
                it.confidence_tier  # type: ignore[arg-type]
                if it.confidence_tier in ("confirmed", "leaning", "hidden")
                else None
            ),
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

    _qw = analysis.quality_warnings
    quality_warnings_out: list[str] = (
        [str(x) for x in _qw] if isinstance(_qw, list) else []
    )

    # P2-W10：W8 引擎诊断从 DB → response（schema EngineWarningItem 自带 Pydantic 校验）
    _ew = getattr(analysis, "engine_warnings", None)
    engine_warnings_out: list[dict] = _ew if isinstance(_ew, list) else []

    phase_highlights_out = build_phase_highlights(
        {k: int(v.get("score", 0)) for k, v in (analysis.phase_scores or {}).items()}
        if isinstance(analysis.phase_scores, dict)
        else None
    )

    return AnalysisReportResponse(
        id=analysis.id,
        user_id=analysis.user_id,
        status=normalize_analysis_status(analysis.status, analysis_id=analysis.id),
        camera_angle=analysis.camera_angle,  # type: ignore[arg-type]
        club_type=analysis.club_type,  # type: ignore[arg-type]
        analysis_mode=getattr(analysis, "analysis_mode", None) or "full_swing",  # type: ignore[arg-type]
        putting_features=_build_putting_features(analysis),
        chipping_features=_build_chipping_features(analysis),
        engine_version=(
            getattr(analysis, "engine_version", None) or "v1"
        ),  # type: ignore[arg-type]
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
        quality_warnings=quality_warnings_out,
        # P2-W10：confidence + engine_warnings 端到端透传
        analysis_confidence=float(getattr(analysis, "analysis_confidence", 1.0) or 1.0),
        feature_confidences=(
            dict(getattr(analysis, "feature_confidences", None) or {})
        ),
        engine_warnings=engine_warnings_out,  # type: ignore[arg-type]
        phase_highlights=phase_highlights_out,
        share_card_url=to_proxy_image_url(analysis.share_card_url),
        analyzed_at=analysis.analyzed_at,
        created_at=analysis.created_at,
    )


# ==================================================================
# 3.5 GET /v1/analyses
# ==================================================================
# 免费用户能看到的历史报告条数上限（docs/01 §8.2）
FREE_HISTORY_VISIBLE_LIMIT = 3


async def list_analyses(
    *,
    user: User,
    query: AnalysisListQuery,
    db: AsyncSession,
    free_user_cap: int | None = None,
) -> tuple[list[AnalysisListItem], int, int | None]:
    """返回 ``(items, total, capped_to)``.

    ``free_user_cap``：若不为 ``None`` 且 ``user.membership_type=='free'``，
    则只返回最近 N 条 items（``total`` 仍是 SQL 真实计数），路由层据此提示
    "升级查看全部"。
    """
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

    apply_cap = (
        free_user_cap is not None
        and free_user_cap > 0
        and user.membership_type == "free"
    )

    offset = (query.page - 1) * query.page_size
    effective_limit = query.page_size
    capped_to: int | None = None
    if apply_cap:
        # 仅在首页（page=1）截断；翻页对 free 用户返回空列表（前端会因 paywall 提示）
        effective_limit = (
            min(query.page_size, free_user_cap) if query.page == 1 else 0
        )
        capped_to = free_user_cap

    rows: list[SwingAnalysis] = []
    if effective_limit > 0:
        rows_stmt = (
            select(SwingAnalysis)
            .where(and_(*conds))
            .order_by(SwingAnalysis.created_at.desc())
            .offset(offset)
            .limit(effective_limit)
        )
        rows = list((await db.execute(rows_stmt)).scalars().all())

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
            # P2-W11：V2 字段透传；V1 老报告 engine_version 缺省 "v1"，analysis_confidence None 让前端不渲染小标签
            engine_version=(
                getattr(r, "engine_version", None) or "v1"
            ),  # type: ignore[arg-type]
            analysis_confidence=_coerce_list_confidence(
                getattr(r, "analysis_confidence", None)
            ),
        )
        for r in rows
    ]
    return items, total, capped_to


# ==================================================================
# MVP 进步曲线数据（§6.1）
# ==================================================================
def _flatten_phase_scores(raw: dict | None) -> dict[str, int] | None:
    """JSONB phase_scores → 扁平 int map（progress 接口专用，减小 payload）。"""
    if not raw or not isinstance(raw, dict):
        return None
    out: dict[str, int] = {}
    for key, val in raw.items():
        if isinstance(val, dict) and val.get("score") is not None:
            out[str(key)] = int(val["score"])
        elif isinstance(val, (int, float)):
            out[str(key)] = int(val)
    return out or None


async def get_user_analysis_progress(
    db: AsyncSession,
    user: User,
    *,
    window_days: int | None = None,
    max_points: int = 500,
) -> AnalysisProgressResponse:
    """进步曲线数据源：按时间升序；`window_days>0` 时只取最近 N 天；`max_points` 防止超大列表。

    `window_days` 为 ``None`` 或 ``0`` 表示不按时间窗截断（仍受 ``max_points`` 限制）。
    """
    from datetime import timedelta

    now = datetime.now(UTC)
    stmt = select(SwingAnalysis).where(
        SwingAnalysis.user_id == user.id,
        SwingAnalysis.is_sample.is_(False),
        SwingAnalysis.deleted_at.is_(None),
        SwingAnalysis.status == "completed",
        SwingAnalysis.overall_score.isnot(None),
    )
    if window_days is not None and window_days > 0:
        cutoff = now - timedelta(days=window_days)
        stmt = stmt.where(
            or_(
                and_(SwingAnalysis.analyzed_at.isnot(None), SwingAnalysis.analyzed_at >= cutoff),
                and_(SwingAnalysis.analyzed_at.is_(None), SwingAnalysis.created_at >= cutoff),
            )
        )
    stmt = (
        stmt.order_by(
            SwingAnalysis.analyzed_at.asc().nulls_last(),
            SwingAnalysis.created_at.asc(),
        ).limit(min(max(max_points, 1), 2000))
    )
    rows = (await db.execute(stmt)).scalars().all()
    pts: list[AnalysisProgressPoint] = [
        AnalysisProgressPoint(
            analysis_id=r.id,
            analyzed_at=r.analyzed_at or r.created_at,
            overall_score=int(r.overall_score or 0),
            phase_scores=_flatten_phase_scores(r.phase_scores),
            # P2-W12-1：透传 V2 字段；老 V1 报告兜底 "v1"，
            # confidence 走 _coerce_list_confidence 防 NaN/Inf/越界
            engine_version=(
                getattr(r, "engine_version", None) or "v1"
            ),  # type: ignore[arg-type]
            analysis_confidence=_coerce_list_confidence(
                getattr(r, "analysis_confidence", None)
            ),
        )
        for r in rows
    ]
    return AnalysisProgressResponse(points=pts)


# ==================================================================
# P2-W16-A · ENG-05 · 同水平 + 同器材的得分分位
# ==================================================================
#
# 历史脉络
# - W12-1：进步曲线接 trust tier 着色（用户能看出"自己曲线"的可信度）
# - **W16-A**：进步曲线之外，加一条横向对比："你击败了 X% 同水平用户"——
#   把"个人 vs 群体"的语义补齐，直接呼应 §5.1 产品白皮书 P-03 / ENG-05。
#
# 维度选择
# - **golf_level**（User 表，beginner/amateur/intermediate/advanced/unknown）→ 心智上"同一档"
# - **club_type**（必传）→ 不同球杆分数分布差很大（小铁杆 70+ vs 一号木 50+）
#
# 与 user_profiles_v2.handicap 的关系
# - 现阶段不接入 handicap：① UPv2 未必所有用户都填；② golf_level 已是用户主动声明的"自我定位"
# - W17+ 等真实流量积累后可加 handicap 二级分桶（如 0-9 / 10-18 / 19+）
#
# 隐私
# - 响应**只**暴露聚合字段（cohort_size / median / percentile）
# - 不返其他用户的 user_id / 具体分数 / 分析记录
#
# 性能边界
# - cohort 查询走 DISTINCT ON (user_id) 等价物，单 club_type 单 level 上限
#   `_PERCENTILE_MAX_COHORT` 行（默认 1000）
# - 调用频率：客户端按"每次进训练页"调一次，足够稀疏

# 样本量阈值：< 5 → percentile=null；UI 隐藏（避免 1-2 人对比就出"击败 50%"）
_PERCENTILE_MIN_COHORT = 5
# 单次查询 cohort 上限：保护 DB（热门 club_type 单 cohort 也不会爆）
_PERCENTILE_MAX_COHORT = 1000

# 人话化标签（前端可直接展示；不在 i18n 表里因为这是 backend 兜底，前端可以再覆盖）
_GOLF_LEVEL_LABELS_ZH: dict[str, str] = {
    "beginner": "初学",
    "amateur": "业余",
    "intermediate": "中级",
    "advanced": "进阶",
    "professional": "职业",
    "unknown": "全部水平",
}

_CLUB_TYPE_LABELS_ZH: dict[str, str] = {
    "driver": "一号木",
    "fairway_wood": "球道木",
    "hybrid": "混合杆",
    "iron_3": "三号铁",
    "iron_4": "四号铁",
    "iron_5": "五号铁",
    "iron_6": "六号铁",
    "iron_7": "七号铁",
    "iron_8": "八号铁",
    "iron_9": "九号铁",
    "wedge_pw": "P 杆",
    "wedge_aw": "A 杆",
    "wedge_sw": "S 杆",
    "wedge_lw": "L 杆",
    "putter": "推杆",
    "other": "其他",
}


def _format_percentile_cohort_label(golf_level: str | None, club_type: str) -> str:
    """W16-A · 拼"中级 / 七号铁"等人话标签；翻译表 fallback 到原始 enum 值."""
    level_zh = _GOLF_LEVEL_LABELS_ZH.get(golf_level or "unknown", "全部水平")
    club_zh = _CLUB_TYPE_LABELS_ZH.get(club_type, club_type)
    return f"{level_zh} / {club_zh}"


def _calc_percentile(user_score: int, cohort_scores: list[int]) -> int | None:
    """W16-A · 把 cohort_scores（不含当前用户）算成 0-100 的整数百分位.

    定义："击败"= cohort 中**严格小于** user_score 的人数占比。
    - cohort 全员 > user_score → 0%
    - cohort 全员 < user_score → 100%
    - 平局（user_score 命中 cohort 中的多个值）→ 不计入"击败"，向下取整即可

    样本量 < `_PERCENTILE_MIN_COHORT` → 返回 None。
    """
    n = len(cohort_scores)
    if n < _PERCENTILE_MIN_COHORT:
        return None
    below = sum(1 for s in cohort_scores if s < user_score)
    pct = (below * 100) // n
    return max(0, min(100, pct))


def _calc_median(scores: list[int]) -> int | None:
    """W16-A · 中位数（P50）；空列表返 None；偶数取下中位数（保 int 不引浮点）."""
    if not scores:
        return None
    sorted_s = sorted(scores)
    return sorted_s[len(sorted_s) // 2]


async def get_user_score_percentile(
    db: AsyncSession,
    user: User,
    *,
    club_type: str,
) -> ScorePercentileResponse:
    """P2-W16-A · ENG-05 · 算用户在同水平+同器材 cohort 中的分位.

    流程：
    1. 取当前用户最近一条 `club_type` 完成态分析的 ``overall_score`` →
       没有 → ``user_score=None``、``percentile=None``、``cohort_size=0`` 直接返回
    2. 取 cohort：所有"同 ``golf_level`` + 同 ``club_type`` 其他用户"的最近一次
       完成态分析的 ``overall_score``。``user.golf_level`` 为 None 时 cohort 不限定 level。
    3. cohort_size < 5 → percentile/median = None（UI 隐藏分位行）
    4. percentile = ``_calc_percentile(user_score, cohort_scores)``
    5. median = ``_calc_median(cohort_scores)``

    SQL 思路：
    - 用 ``DISTINCT ON`` 等价：取每个 user 最新的一条同 club_type 完成态分析；PG 用
      `ROW_NUMBER()` 窗口或 ``DISTINCT ON``
    - SQLAlchemy 这里用子查询 + ``func.row_number()``，保留 SQLAlchemy 2.x async 风格
    """
    now = datetime.now(UTC)

    # === 1. 当前用户的最近一次同 club_type 综合分 ===
    user_score_stmt = (
        select(SwingAnalysis.overall_score)
        .where(
            SwingAnalysis.user_id == user.id,
            SwingAnalysis.club_type == club_type,
            SwingAnalysis.is_sample.is_(False),
            SwingAnalysis.deleted_at.is_(None),
            SwingAnalysis.status == "completed",
            SwingAnalysis.overall_score.isnot(None),
        )
        .order_by(
            SwingAnalysis.analyzed_at.desc().nulls_last(),
            SwingAnalysis.created_at.desc(),
        )
        .limit(1)
    )
    user_score_row = (await db.execute(user_score_stmt)).scalar_one_or_none()
    user_score = int(user_score_row) if user_score_row is not None else None

    # === 2. cohort 用户的最近一次同 club_type 综合分 ===
    # 用窗口函数取每 user 最新一条
    rn_col = func.row_number().over(
        partition_by=SwingAnalysis.user_id,
        order_by=(
            SwingAnalysis.analyzed_at.desc().nulls_last(),
            SwingAnalysis.created_at.desc(),
        ),
    ).label("rn")
    inner = (
        select(
            SwingAnalysis.user_id.label("uid"),
            SwingAnalysis.overall_score.label("score"),
            rn_col,
        )
        .where(
            SwingAnalysis.user_id != user.id,
            SwingAnalysis.club_type == club_type,
            SwingAnalysis.is_sample.is_(False),
            SwingAnalysis.deleted_at.is_(None),
            SwingAnalysis.status == "completed",
            SwingAnalysis.overall_score.isnot(None),
        )
    ).subquery()

    cohort_stmt = (
        select(inner.c.score)
        .select_from(inner.join(User, User.id == inner.c.uid))
        .where(inner.c.rn == 1, User.deleted_at.is_(None))
    )
    if user.golf_level:
        cohort_stmt = cohort_stmt.where(User.golf_level == user.golf_level)
    cohort_stmt = cohort_stmt.limit(_PERCENTILE_MAX_COHORT)

    cohort_scores: list[int] = [
        int(s) for s in (await db.execute(cohort_stmt)).scalars().all() if s is not None
    ]

    # === 3-5. 计算 ===
    if user_score is None:
        percentile = None
        median = None
    else:
        percentile = _calc_percentile(user_score, cohort_scores)
        median = (
            _calc_median(cohort_scores)
            if len(cohort_scores) >= _PERCENTILE_MIN_COHORT
            else None
        )

    return ScorePercentileResponse(
        user_score=user_score,
        percentile=percentile,
        cohort_size=len(cohort_scores),
        cohort_label=_format_percentile_cohort_label(user.golf_level, club_type),
        median=median,
        club_type=club_type,
        golf_level=user.golf_level,
        computed_at=now,
    )


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
