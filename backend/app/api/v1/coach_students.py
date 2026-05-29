"""M8-03 · 教练侧学员绑定 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_coach_role_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.coach_student import (
    CoachStudentInviteRequest,
    CoachStudentListResponse,
    CoachStudentRelationRead,
    CoachStudentSharedFieldResponse,
)
from app.services import coach_student_service as csr_svc

router = APIRouter()


@router.post(
    "/students/invite",
    summary="邀请学员绑定（M8-03）",
    response_model=APIResponse[CoachStudentRelationRead],
)
async def invite_student(
    body: CoachStudentInviteRequest,
    coach: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
):
    data = await csr_svc.invite_student(db, coach=coach, payload=body)
    await db.commit()
    return ok(data)


@router.get(
    "/students",
    summary="教练查看学员列表（M8-03）",
    response_model=APIResponse[CoachStudentListResponse],
)
async def list_coach_students(
    status: str | None = Query(default=None),
    coach: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
):
    data = await csr_svc.list_coach_students(db, coach=coach, status=status)
    return ok(data)


@router.post(
    "/students/{relation_id}/end",
    summary="教练解除师生关系（M8-03）",
    response_model=APIResponse[CoachStudentRelationRead],
)
async def coach_end_relation(
    relation_id: str,
    coach: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
):
    data = await csr_svc.end_relation(db, user=coach, relation_id=relation_id)
    await db.commit()
    return ok(data)


@router.get(
    "/students/{student_id}/shared-profile",
    summary="按可见性读取学员字段（M8-03）",
    response_model=APIResponse[CoachStudentSharedFieldResponse],
)
async def coach_shared_profile_field(
    student_id: str,
    field: str = Query(..., min_length=1),
    coach: User = Depends(get_coach_role_user),
    db: AsyncSession = Depends(get_db),
):
    data = await csr_svc.get_shared_field_for_coach(
        db, coach=coach, student_id=student_id, field=field
    )
    return ok(data)
