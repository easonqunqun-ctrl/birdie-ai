"""挥杆分析相关接口（对齐 docs/02-API接口设计文档.md §三）."""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.api.v1.pros import _ensure_pros_enabled
from app.core.database import get_db
from app.core.redis import get_redis
from app.integrations.minio import MinioStorageClient, get_minio_storage
from app.models.user import User
from app.schemas.analysis import (
    AnalysisListPage,
    AnalysisListPaywall,
    AnalysisListQuery,
    AnalysisReportResponse,
    AnalysisStatusResponse,
    CameraAngle,
    ClubType,
    CreateAnalysisRequest,
    CreateAnalysisResponse,
    ShareCardResponse,
    UploadTokenRequest,
    UploadTokenResponse,
)
from app.schemas.base import APIResponse, ok
from app.schemas.coach_annotation import CoachAnnotationClipRefRead
from app.schemas.pro_library import ProMatchItemRead, ProMatchResultRead, ProPlayerRead, ProSwingClipRead
from app.services import analysis_service, coach_annotation_service, pro_match_service
from app.services.analysis_service import FREE_HISTORY_VISIBLE_LIMIT, _load_owned
from app.services.sample_fixture import build_sample_report
from app.services.share_card_service import ensure_share_wxa_code_url

router = APIRouter()


# 注意：本路由必须注册在 /{analysis_id} 之前，否则会被 path 参数捕获。
@router.get(
    "/sample",
    summary="获取示例分析报告（免配额、免建任务）",
    description=(
        "MVP §3.6 示例视频体验入口：返回一份固定的演示报告，用于新用户"
        "在真正上传视频之前感受产品价值。**不入库、不计配额**；`id` 固定为 `sample`。"
    ),
    response_model=APIResponse[AnalysisReportResponse],
)
async def get_sample_analysis(
    # 允许匿名；这里仍尝试识别 Authorization，用于未来埋点但不做鉴权
    _user: User | None = Depends(get_current_user_optional),
):
    return ok(build_sample_report())


@router.post(
    "/upload-token",
    summary="获取视频上传凭证",
    response_model=APIResponse[UploadTokenResponse],
)
async def get_upload_token(
    payload: UploadTokenRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    storage: MinioStorageClient = Depends(get_minio_storage),
):
    result = await analysis_service.create_upload_token(
        user=user,
        payload=payload,
        db=db,
        redis=redis,
        storage=storage,
    )
    await db.commit()
    return ok(result)


@router.post(
    "/uploads/{upload_id}/video",
    summary="经 API 上报视频（小程序同源兜底）",
)
async def upload_analysis_video(
    upload_id: str,
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
    storage: MinioStorageClient = Depends(get_minio_storage),
    file: UploadFile = File(..., description="视频文件，字段名 file"),
):
    """与 `upload-token` 配套：客户端用 `wx.uploadFile` 直传至此 URL（multipart 单文件 `file`）。

    写入 MinIO/COS 后刷新 Redis 内 `file_size` 为实际上传字节数，以便 `POST /analyses` 校验通过。
    """
    body = await file.read()
    await analysis_service.receive_upload_via_api(
        user=user,
        upload_id=upload_id,
        file_body=body,
        redis=redis,
        storage=storage,
    )
    return ok(None)


@router.post(
    "",
    summary="创建挥杆分析任务",
    response_model=APIResponse[CreateAnalysisResponse],
)
async def create_analysis(
    payload: CreateAnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    storage: MinioStorageClient = Depends(get_minio_storage),
):
    result = await analysis_service.create_analysis(
        user=user,
        payload=payload,
        db=db,
        redis=redis,
        storage=storage,
    )
    await db.commit()
    await analysis_service.finalize_analysis_dispatch_after_commit(
        redis=redis,
        upload_id=payload.upload_id,
        analysis_id=result.analysis_id,
    )
    return ok(result, message="分析任务已创建")


@router.get(
    "/{analysis_id}/status",
    summary="查询分析状态",
    response_model=APIResponse[AnalysisStatusResponse],
)
async def get_analysis_status(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await analysis_service.get_status(analysis_id=analysis_id, user=user, db=db)
    return ok(result)


@router.post(
    "/{analysis_id}/share-card",
    summary="生成分享用小程序码 PNG URL（对象存储缓存）",
    response_model=APIResponse[ShareCardResponse],
)
async def create_share_card(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: MinioStorageClient = Depends(get_minio_storage),
):
    url = await ensure_share_wxa_code_url(
        db=db, user=user, analysis_id=analysis_id, storage=storage
    )
    await db.commit()
    return ok(ShareCardResponse(wxa_code_url=url))


@router.get(
    "/{analysis_id}",
    summary="获取分析报告详情",
    response_model=APIResponse[AnalysisReportResponse],
)
async def get_analysis_report(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await analysis_service.get_report(analysis_id=analysis_id, user=user, db=db)
    return ok(result)


@router.get(
    "/{analysis_id}/pro-matches",
    summary="匹配最相似的职业球手镜头（M12-04）",
    response_model=APIResponse[ProMatchResultRead],
)
async def get_analysis_pro_matches(
    analysis_id: str,
    limit: int = Query(5, ge=1, le=10, description="返回 Top-N 匹配"),
    record: bool = Query(
        True, description="是否将 Top-1 写入 user_pro_match_history"
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_pros_enabled()
    analysis = await _load_owned(db, analysis_id, user)
    matches, history = await pro_match_service.match_analysis_to_pro_clips(
        db,
        user_id=user.id,
        analysis=analysis,
        limit=limit,
        record=record,
    )
    await db.commit()
    items = [
        ProMatchItemRead(
            match_score=m.match_score,
            match_details=m.match_details,
            clip=ProSwingClipRead.model_validate(m.clip),
            player=ProPlayerRead.model_validate(m.player),
        )
        for m in matches
    ]
    return ok(
        ProMatchResultRead(
            analysis_id=analysis_id,
            matches=items,
            recorded_match_id=history.id if history else None,
        )
    )


@router.get(
    "/{analysis_id}/coach-annotations",
    summary="学员查看教练批注（M12-09）",
    response_model=APIResponse[list[CoachAnnotationClipRefRead]],
)
async def list_analysis_coach_annotations(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await coach_annotation_service.list_student_annotations(
        db, student=user, analysis_id=analysis_id
    )
    return ok(items)


@router.delete(
    "/{analysis_id}",
    summary="软删除分析报告",
    response_model=APIResponse[None],
)
async def delete_analysis(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await analysis_service.delete_analysis_for_user(
        analysis_id=analysis_id, user=user, db=db
    )
    await db.commit()
    return ok(None, message="报告已删除")


@router.get(
    "",
    summary="获取分析历史列表",
    description=(
        "免费用户（``membership_type='free'``）只会看到最近 "
        f"{FREE_HISTORY_VISIBLE_LIMIT} 份；超出时返回 ``paywall`` 字段，"
        "前端据此展示「升级会员查看全部 N 份」CTA。"
    ),
    response_model=APIResponse[AnalysisListPage],
)
async def list_analyses(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    club_type: ClubType | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    camera_angle: CameraAngle | None = Query(default=None, include_in_schema=False),  # 预留
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = AnalysisListQuery(
        page=page,
        page_size=page_size,
        club_type=club_type,
        date_from=date_from,
        date_to=date_to,
    )
    items, total, capped_to = await analysis_service.list_analyses(
        user=user,
        query=query,
        db=db,
        free_user_cap=FREE_HISTORY_VISIBLE_LIMIT,
    )
    paywall: AnalysisListPaywall | None = None
    if capped_to is not None and total > capped_to:
        paywall = AnalysisListPaywall(capped_to=capped_to, total_count=total)
    # 当前已返回数 + 上一页累计 ≥ 总数则 has_more=False；首页对 free 用户被截断也算到此。
    # 免费用户：把"可见上限"当作 has_more 判定的真上限。
    delivered = (query.page - 1) * query.page_size + len(items)
    has_more = (
        delivered < min(total, capped_to)
        if capped_to is not None
        else delivered < total
    )
    return ok(
        AnalysisListPage(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            has_more=has_more,
            paywall=paywall,
        )
    )
