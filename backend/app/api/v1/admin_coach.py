"""M8-01 · 教练资质审核 Admin API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.coach_profile import (
    CoachReviewStatusLiteral,
    CoachVerificationListResponse,
    CoachVerificationRead,
    CoachVerificationReview,
)
from app.services import coach_profile_service as coach_svc

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
