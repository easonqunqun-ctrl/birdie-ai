"""M8-10 · 种子教练 BD：level=seed 标记 + 一年高级权益."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.models.coach import CoachProfile
from app.models.user import User
from app.schemas.coach_profile import (
    CoachLevelLiteral,
    CoachProfileListResponse,
    CoachProfileRead,
    GrantSeedPremiumResponse,
)
from app.services import payment_service
from app.services.coach_profile_service import (
    assert_admin,
    ensure_coach_module_enabled,
    get_profile,
)
from app.services.user_service import get_user_by_id

logger = get_logger("coach_seed")

SEED_LEVEL: CoachLevelLiteral = "seed"


async def list_profiles_for_admin(
    db: AsyncSession,
    *,
    level: CoachLevelLiteral | None = None,
    status: str | None = "active",
    limit: int = 50,
) -> CoachProfileListResponse:
    limit = max(1, min(limit, 100))
    stmt = select(CoachProfile).order_by(CoachProfile.applied_at.desc()).limit(limit)
    if level is not None:
        stmt = stmt.where(CoachProfile.level == level)
    if status is not None:
        stmt = stmt.where(CoachProfile.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    items = [CoachProfileRead.model_validate(p) for p in rows]
    return CoachProfileListResponse(items=items, total=len(items))


async def set_seed_level(
    db: AsyncSession,
    *,
    admin: User,
    coach_user_id: str,
    level: CoachLevelLiteral,
) -> CoachProfileRead:
    ensure_coach_module_enabled()
    assert_admin(admin)
    profile = await get_profile(db, user_id=coach_user_id)
    if profile is None:
        raise NotFoundError(code=40406, message="教练档案不存在")
    if profile.status != "active":
        raise BadRequestError(code=40001, message="仅 active 教练可标记种子身份")
    profile.level = level
    await db.flush()
    logger.info(
        "coach_seed_level_updated",
        extra={"coach_user_id": coach_user_id, "level": level, "admin_id": admin.id},
    )
    return CoachProfileRead.model_validate(profile)


async def grant_seed_premium(
    db: AsyncSession,
    *,
    admin: User | None,
    coach_user_id: str,
    valid_days: int = 365,
) -> GrantSeedPremiumResponse:
    ensure_coach_module_enabled()
    if admin is not None:
        assert_admin(admin)

    profile = await get_profile(db, user_id=coach_user_id)
    if profile is None:
        raise NotFoundError(code=40406, message="教练档案不存在")
    if profile.level != SEED_LEVEL:
        raise BadRequestError(code=40001, message="仅 level=seed 的教练可开通种子权益")
    if profile.status != "active":
        raise BadRequestError(code=40001, message="教练档案须为 active")

    user = await get_user_by_id(db, coach_user_id)
    new_end = await payment_service.grant_complimentary_membership(
        db,
        user,
        duration_days=valid_days,
        plan_type="yearly",
    )
    logger.info(
        "grant_seed_premium",
        extra={
            "coach_user_id": coach_user_id,
            "valid_days": valid_days,
            "operator_id": admin.id if admin else None,
            "expires_at": new_end.isoformat(),
        },
    )
    return GrantSeedPremiumResponse(
        user_id=user.id,
        membership_type=user.membership_type,
        membership_expires_at=new_end,
        granted_days=valid_days,
    )
