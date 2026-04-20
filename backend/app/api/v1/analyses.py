"""挥杆分析相关接口（对齐 docs/02-API接口设计文档.md §三）."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional
from app.core.database import get_db
from app.core.redis import get_redis
from app.integrations.minio import MinioStorageClient, get_minio_storage
from app.models.user import User
from app.schemas.analysis import (
    AnalysisListItem,
    AnalysisListQuery,
    AnalysisReportResponse,
    AnalysisStatusResponse,
    CameraAngle,
    ClubType,
    CreateAnalysisRequest,
    CreateAnalysisResponse,
    UploadTokenRequest,
    UploadTokenResponse,
)
from app.schemas.base import APIResponse, PageData, ok, page_data
from app.services import analysis_service
from app.services.sample_fixture import build_sample_report

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
    "",
    summary="获取分析历史列表",
    response_model=APIResponse[PageData[AnalysisListItem]],
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
    items, total = await analysis_service.list_analyses(user=user, query=query, db=db)
    return ok(page_data(items, total=total, page=query.page, page_size=query.page_size))
