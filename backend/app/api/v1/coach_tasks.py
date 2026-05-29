"""M8-05 · 教练作业派发 API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_coach_role_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.coach_task import (
    CoachAssignedTaskListResponse,
    CoachAssignedTaskRead,
    CoachTaskAssignRequest,
)
from app.services import coach_task_service as task_svc

router = APIRouter()


@router.post(
    "/tasks/assign",
    summary="教练派发训练作业（M8-05）",
    response_model=APIResponse[CoachAssignedTaskRead],
)
async def assign_coach_task(
    payload: CoachTaskAssignRequest,
    user: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
):
    item = await task_svc.assign_task(db, coach=user, payload=payload)
    await db.commit()
    return ok(item)


@router.get(
    "/tasks",
    summary="教练查看已派发作业（M8-05）",
    response_model=APIResponse[CoachAssignedTaskListResponse],
)
async def list_coach_tasks(
    student_user_id: Annotated[str | None, Query(alias="student_id")] = None,
    status: Annotated[str | None, Query()] = None,
    user: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
):
    items = await task_svc.list_coach_tasks(
        db,
        coach=user,
        student_user_id=student_user_id,
        status=status,
    )
    return ok(items)
