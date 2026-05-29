"""M13-07 · 约球互评 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.meetup import (
    FeedbackRead,
    MeetupFeedbackEligibility,
    MeetupFeedbackListResponse,
    MeetupFeedbackSubmit,
)
from app.services import meetup_feedback_service as feedback_svc

router = APIRouter()
me_router = APIRouter()


def _ensure_meetup_enabled() -> None:
    if not settings.PHASE2_MEETUP_ENABLED:
        raise NotFoundError(code=40406, message="约球功能未开放")


@router.post(
    "/feedbacks",
    summary="提交约球互评（M13-07）",
    response_model=APIResponse[FeedbackRead],
)
async def submit_meetup_feedback(
    payload: MeetupFeedbackSubmit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_meetup_enabled()
    fb = await feedback_svc.submit_feedback(
        db, reviewer_user_id=user.id, payload=payload
    )
    await db.commit()
    return ok(FeedbackRead.model_validate(fb))


@router.get(
    "/feedbacks",
    summary="按邀请查询互评（24h 隔离，M13-07）",
    response_model=APIResponse[MeetupFeedbackListResponse],
)
async def list_meetup_feedbacks_for_invitation(
    invitation_id: str = Query(..., max_length=32),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_meetup_enabled()
    items = await feedback_svc.list_feedbacks_for_invitation(
        db, viewer_user_id=user.id, invitation_id=invitation_id
    )
    return ok(
        MeetupFeedbackListResponse(
            items=items,
            total=len(items),
            invitation_id=invitation_id,
        )
    )


@router.get(
    "/feedbacks/eligibility",
    summary="互评资格查询（M13-07）",
    response_model=APIResponse[MeetupFeedbackEligibility],
)
async def get_meetup_feedback_eligibility(
    invitation_id: str = Query(..., max_length=32),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_meetup_enabled()
    data = await feedback_svc.get_feedback_eligibility(
        db, user_id=user.id, invitation_id=invitation_id
    )
    return ok(MeetupFeedbackEligibility.model_validate(data))


@me_router.get(
    "/meetup-feedbacks",
    summary="我的约球互评列表（M13-07）",
    response_model=APIResponse[MeetupFeedbackListResponse],
)
async def list_my_meetup_feedbacks(
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_meetup_enabled()
    items = await feedback_svc.list_my_feedbacks(db, user_id=user.id, limit=limit)
    return ok(MeetupFeedbackListResponse(items=items, total=len(items)))
