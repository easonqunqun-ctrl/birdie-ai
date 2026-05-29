"""M8-04 / M12-09 · 教练报告批注 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_coach_role_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.coach_annotation import CoachAnnotationClipRefRead, CoachAnnotationCreate
from app.services import coach_annotation_service as ann_svc

router = APIRouter()


@router.get(
    "/analyses/{analysis_id}/annotations",
    summary="教练列出分析报告批注（M12-09）",
    response_model=APIResponse[list[CoachAnnotationClipRefRead]],
)
async def list_coach_analysis_annotations(
    analysis_id: str,
    user: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
):
    items = await ann_svc.list_coach_annotations(db, coach=user, analysis_id=analysis_id)
    return ok(items)


@router.post(
    "/analyses/{analysis_id}/annotations",
    summary="教练创建 video_ref 批注（M12-09）",
    response_model=APIResponse[CoachAnnotationClipRefRead],
)
async def create_coach_analysis_annotation(
    analysis_id: str,
    payload: CoachAnnotationCreate,
    user: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
):
    item = await ann_svc.create_annotation(
        db, coach=user, analysis_id=analysis_id, payload=payload
    )
    await db.commit()
    return ok(item)


@router.delete(
    "/annotations/{annotation_id}",
    summary="教练删除批注（M12-09）",
    response_model=APIResponse[dict],
)
async def delete_coach_annotation(
    annotation_id: str,
    user: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
):
    await ann_svc.delete_annotation(db, coach=user, annotation_id=annotation_id)
    await db.commit()
    return ok({})
