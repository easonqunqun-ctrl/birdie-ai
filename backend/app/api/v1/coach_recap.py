"""M8-07 · 教练教学报告 API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_coach_role_user
from app.core.database import get_db
from app.integrations.minio import MinioStorageClient, get_minio_storage
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.coach_recap import (
    CoachRecapCreateRequest,
    CoachRecapCreateResponse,
    CoachRecapExportPdfResponse,
    CoachRecapListResponse,
)
from app.services import coach_recap_service as recap_svc

router = APIRouter()


@router.post(
    "/sessions/recap",
    summary="生成课程教学报告 LLM 汇总（M8-07）",
    response_model=APIResponse[CoachRecapCreateResponse],
)
async def create_session_recap(
    payload: CoachRecapCreateRequest,
    coach: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
):
    data = await recap_svc.create_recap(db, coach=coach, payload=payload)
    await db.commit()
    return ok(data)


@router.post(
    "/sessions/{recap_id}/export-pdf",
    summary="导出教学报告 PDF（M8-07）",
    response_model=APIResponse[CoachRecapExportPdfResponse],
)
async def export_session_recap_pdf(
    recap_id: str,
    coach: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
    storage: MinioStorageClient = Depends(get_minio_storage),
):
    data = await recap_svc.export_recap_pdf(
        db, coach=coach, recap_id=recap_id, storage=storage
    )
    await db.commit()
    return ok(data)


@router.get(
    "/sessions/recaps",
    summary="教练教学报告列表（M8-07）",
    response_model=APIResponse[CoachRecapListResponse],
)
async def list_session_recaps(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    coach: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
    storage: MinioStorageClient = Depends(get_minio_storage),
):
    data = await recap_svc.list_recaps(
        db, coach=coach, page=page, page_size=page_size, storage=storage
    )
    return ok(data)
