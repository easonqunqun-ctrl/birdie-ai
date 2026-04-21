"""用户相关接口."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import BadRequestError
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.user import (
    OnboardingRequest,
    UserQuota,
    UserResponse,
    UserStats,
    UserUpdateRequest,
)
from app.services import payment_service, quota_service

router = APIRouter()


def _build_user_response(user: User, *, include_stats: bool = True) -> UserResponse:
    return UserResponse(
        id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        golf_level=user.golf_level,
        primary_goals=user.primary_goals or [],
        weekly_practice_frequency=user.weekly_practice_frequency,
        membership_type=user.membership_type,
        membership_expires_at=user.membership_expires_at,
        is_member=payment_service.is_member(user),
        membership_days_remaining=payment_service.days_remaining(user),
        onboarding_completed=user.onboarding_completed,
        stats=UserStats(
            total_analyses=user.total_analyses,
            total_practices=user.total_practices,
            streak_days=user.current_streak_days,
            best_score=user.best_score,
            score_improvement=0,
        ) if include_stats else None,
        quota=None,
        created_at=user.created_at,
    )


@router.get(
    "/me",
    summary="获取当前用户信息",
    response_model=APIResponse[UserResponse],
)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a_quota = await quota_service.get_or_create_analysis_quota(db, user)
    c_quota = await quota_service.get_or_create_chat_quota(db, user)
    await db.commit()

    resp = _build_user_response(user)
    resp.quota = UserQuota(
        analysis_remaining=quota_service.analysis_remaining(a_quota),
        analysis_total=a_quota.total + a_quota.bonus if a_quota.total >= 0 else 9999,
        analysis_reset_at=quota_service.next_month_reset_iso(),
        chat_remaining_today=quota_service.chat_remaining(c_quota),
        chat_total_today=c_quota.total if c_quota.total >= 0 else 9999,
    )
    return ok(resp)


@router.post(
    "/me/onboarding",
    summary="完成新用户引导",
    response_model=APIResponse[UserResponse],
)
async def complete_onboarding(
    payload: OnboardingRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.golf_level = payload.golf_level
    user.primary_goals = list(payload.primary_goals)
    user.weekly_practice_frequency = payload.weekly_practice_frequency
    user.onboarding_completed = True
    await db.commit()
    await db.refresh(user)
    return ok(_build_user_response(user, include_stats=False))


@router.patch(
    "/me",
    summary="更新当前用户信息",
    response_model=APIResponse[UserResponse],
)
async def update_me(
    payload: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_dict = payload.model_dump(exclude_unset=True)
    # 语义守门：PATCH /me 仅允许把 onboarding_completed 从 false 置为 true（"跳过"入口），
    # 不允许通过该接口反向置 false（那应由专门的重置/注销逻辑承担）。
    if update_dict.get("onboarding_completed") is False:
        raise BadRequestError(code=40010, message="不允许将 onboarding_completed 置为 false")
    for k, v in update_dict.items():
        setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    return ok(_build_user_response(user))
