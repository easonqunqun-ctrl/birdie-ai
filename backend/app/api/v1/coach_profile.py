"""M8-01 · 教练档案 / 资质申请 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.coach_profile import CoachProfileApply, CoachProfileRead
from app.services import coach_profile_service as coach_svc

router = APIRouter()


@router.post(
    "/profile/apply",
    summary="申请成为教练（M8-01）",
    response_model=APIResponse[CoachProfileRead],
)
async def apply_coach_profile(
    payload: CoachProfileApply,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coach_svc.ensure_coach_module_enabled()
    profile = await coach_svc.apply_profile(db, user=user, payload=payload)
    await db.commit()
    return ok(profile)


@router.get(
    "/profile/me",
    summary="查询我的教练档案（M8-01）",
    response_model=APIResponse[CoachProfileRead | None],
)
async def get_my_coach_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coach_svc.ensure_coach_module_enabled()
    profile = await coach_svc.get_my_profile(db, user=user)
    return ok(profile)
