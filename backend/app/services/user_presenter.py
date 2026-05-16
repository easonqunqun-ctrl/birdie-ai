"""用户 ORM → `UserResponse`：清洗 JSONB / 历史脏数据，避免 ValidationError → HTTP 500."""

from app.models.user import User
from app.schemas.user import (
    UserResponse,
    UserStats,
    sanitize_membership_type_for_response,
    sanitize_optional_golf_level,
    sanitize_optional_weekly_freq,
    sanitize_primary_goals_for_response,
)
from app.services import payment_service


def build_user_response(user: User, *, include_stats: bool = True) -> UserResponse:
    return UserResponse(
        id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        golf_level=sanitize_optional_golf_level(user.golf_level),
        primary_goals=sanitize_primary_goals_for_response(user.primary_goals),
        weekly_practice_frequency=sanitize_optional_weekly_freq(user.weekly_practice_frequency),
        membership_type=sanitize_membership_type_for_response(user.membership_type),
        membership_expires_at=user.membership_expires_at,
        is_member=payment_service.is_member(user),
        membership_days_remaining=payment_service.days_remaining(user),
        onboarding_completed=user.onboarding_completed,
        stats=UserStats(
            total_analyses=int(user.total_analyses or 0),
            total_practices=int(user.total_practices or 0),
            streak_days=int(user.current_streak_days or 0),
            best_score=int(user.best_score or 0),
            score_improvement=0,
        )
        if include_stats
        else None,
        quota=None,
        created_at=user.created_at,
        account_deletion_scheduled_at=user.account_deletion_scheduled_at,
    )
