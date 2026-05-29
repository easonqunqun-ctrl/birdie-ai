"""M13-10 · 教练旁观学员约球 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.coach_spectator import CoachStudentMeetupsResponse
from app.services import coach_spectator_service as spectator_svc

router = APIRouter()


@router.get(
    "/students/{student_id}/meetups",
    summary="教练查看学员约球（M13-10，去识别对方）",
    response_model=APIResponse[CoachStudentMeetupsResponse],
)
async def list_coach_student_meetups(
    student_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await spectator_svc.list_student_meetups_for_coach(
        db,
        coach=user,
        student_id=student_id,
        page=page,
        page_size=page_size,
    )
    await db.commit()
    return ok(data)
