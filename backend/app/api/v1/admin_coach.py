"""M8-01 · 教练资质审核 Admin API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.coach_profile import (
    CoachLevelLiteral,
    CoachProfileListResponse,
    CoachProfileRead,
    CoachReviewStatusLiteral,
    CoachSeedLevelUpdate,
    CoachVerificationListResponse,
    CoachVerificationRead,
    CoachVerificationReview,
    GrantSeedPremiumRequest,
    GrantSeedPremiumResponse,
)
from app.services import coach_profile_service as coach_svc
from app.services import coach_seed_service as seed_svc

router = APIRouter()


@router.get(
    "/coach/verifications",
    summary="待审教练资质列表（M8-01 Admin）",
    response_model=APIResponse[CoachVerificationListResponse],
)
async def list_coach_verifications(
    status: CoachReviewStatusLiteral = Query("pending"),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coach_svc.ensure_coach_module_enabled()
    coach_svc.assert_admin(user)
    data = await coach_svc.list_verifications_for_admin(db, status=status, limit=limit)
    return ok(data)


@router.post(
    "/coach/verifications/{verification_id}/review",
    summary="审核教练资质（M8-01 Admin）",
    response_model=APIResponse[CoachVerificationRead],
)
async def review_coach_verification(
    verification_id: str,
    payload: CoachVerificationReview,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coach_svc.ensure_coach_module_enabled()
    item = await coach_svc.review_verification(
        db,
        admin=user,
        verification_id=verification_id,
        payload=payload,
    )
    await db.commit()
    return ok(item)


@router.get(
    "/coach/profiles",
    summary="教练档案列表（M8-10 Admin · 种子筛选）",
    response_model=APIResponse[CoachProfileListResponse],
)
async def list_coach_profiles(
    level: CoachLevelLiteral | None = Query(default=None),
    status: str | None = Query(default="active"),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coach_svc.ensure_coach_module_enabled()
    coach_svc.assert_admin(user)
    data = await seed_svc.list_profiles_for_admin(
        db, level=level, status=status, limit=limit
    )
    return ok(data)


@router.patch(
    "/coach/profiles/{coach_user_id}/level",
    summary="标记/取消种子教练 level（M8-10 Admin）",
    response_model=APIResponse[CoachProfileRead],
)
async def update_coach_seed_level(
    coach_user_id: str,
    payload: CoachSeedLevelUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coach_svc.ensure_coach_module_enabled()
    profile = await seed_svc.set_seed_level(
        db,
        admin=user,
        coach_user_id=coach_user_id,
        level=payload.level,
    )
    await db.commit()
    return ok(profile)


@router.post(
    "/coach/profiles/{coach_user_id}/grant-seed-premium",
    summary="开通种子教练一年高级权益（M8-10 Admin / BD 脚本）",
    response_model=APIResponse[GrantSeedPremiumResponse],
)
async def grant_coach_seed_premium(
    coach_user_id: str,
    payload: GrantSeedPremiumRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    coach_svc.ensure_coach_module_enabled()
    result = await seed_svc.grant_seed_premium(
        db,
        admin=user,
        coach_user_id=coach_user_id,
        valid_days=payload.valid_days,
    )
    await db.commit()
    return ok(result)
