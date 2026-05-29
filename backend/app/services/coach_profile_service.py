"""M8-01 · 教练档案 / 资质审核 service."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    BadRequestError,
    CoachNotVerifiedError,
    CoachVerificationRejectedError,
    ForbiddenError,
    NotFoundError,
)
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.coach import CoachProfile, CoachVerification
from app.models.user import User
from app.schemas.coach_profile import (
    CoachProfileApply,
    CoachProfileBrief,
    CoachProfileRead,
    CoachVerificationListResponse,
    CoachVerificationRead,
    CoachVerificationReview,
)
from app.services.coach_course_service import coach_course_user_ids

logger = get_logger("coach_profile")

VALID_PROFILE_STATUSES = frozenset({"pending", "active", "rejected", "paused"})
VALID_REVIEW_STATUSES = frozenset({"pending", "approved", "rejected", "need_more"})


def ensure_coach_module_enabled() -> None:
    if not settings.PHASE2_COACH_ENABLED:
        raise NotFoundError(code=40406, message="教练功能未开放")


def admin_user_ids() -> frozenset[str]:
    raw = (settings.ADMIN_USER_IDS or "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def assert_admin(user: User) -> None:
    if user.id not in admin_user_ids():
        raise ForbiddenError(code=40301, message="无权访问管理端点")


def is_seed_coach(user_id: str) -> bool:
    return user_id in coach_course_user_ids()


async def is_active_coach(db: AsyncSession, *, user_id: str) -> bool:
    if is_seed_coach(user_id):
        return True
    profile = await db.get(CoachProfile, user_id)
    return profile is not None and profile.status == "active"


async def assert_active_coach(db: AsyncSession, *, user: User) -> None:
    if is_seed_coach(user.id):
        return
    profile = await db.get(CoachProfile, user.id)
    if profile is None or profile.status != "active":
        raise CoachNotVerifiedError()


def _now() -> datetime:
    return datetime.now(UTC)


async def get_profile(db: AsyncSession, *, user_id: str) -> CoachProfile | None:
    return await db.get(CoachProfile, user_id)


async def get_profile_brief(db: AsyncSession, *, user_id: str) -> CoachProfileBrief | None:
    profile = await get_profile(db, user_id=user_id)
    if profile is None:
        return None
    return CoachProfileBrief.model_validate(profile)


async def get_my_profile(db: AsyncSession, *, user: User) -> CoachProfileRead | None:
    ensure_coach_module_enabled()
    profile = await get_profile(db, user_id=user.id)
    if profile is None:
        return None
    latest = await _latest_verification(db, user_id=user.id)
    data = CoachProfileRead.model_validate(profile)
    if latest is not None:
        return data.model_copy(
            update={
                "latest_verification_id": latest.id,
                "latest_review_status": latest.review_status,  # type: ignore[arg-type]
            }
        )
    return data


async def _latest_verification(
    db: AsyncSession, *, user_id: str
) -> CoachVerification | None:
    row = await db.execute(
        select(CoachVerification)
        .where(CoachVerification.user_id == user_id)
        .order_by(CoachVerification.submitted_at.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


async def apply_profile(
    db: AsyncSession, *, user: User, payload: CoachProfileApply
) -> CoachProfileRead:
    ensure_coach_module_enabled()
    existing = await get_profile(db, user_id=user.id)
    now = _now()

    if existing is not None and existing.status == "active":
        raise BadRequestError(code=40001, message="已是认证教练，无需重复申请")
    if existing is not None and existing.status == "pending":
        raise BadRequestError(code=40903, message="申请审核中，请耐心等待")

    if existing is None:
        profile = CoachProfile(
            user_id=user.id,
            display_name=payload.display_name,
            avatar_url=payload.avatar_url,
            level=payload.level,
            bio=payload.bio,
            certifications=[c.model_dump(exclude_none=True) for c in payload.certifications],
            specialties=list(payload.specialties),
            service_cities=list(payload.service_cities),
            status="pending",
            applied_at=now,
        )
        db.add(profile)
    else:
        profile = existing
        profile.display_name = payload.display_name
        profile.avatar_url = payload.avatar_url
        profile.level = payload.level
        profile.bio = payload.bio
        profile.certifications = [
            c.model_dump(exclude_none=True) for c in payload.certifications
        ]
        profile.specialties = list(payload.specialties)
        profile.service_cities = list(payload.service_cities)
        profile.status = "pending"
        profile.applied_at = now
        profile.approved_at = None
        profile.rejected_at = None

    verification = CoachVerification(
        id=new_id("cvr"),
        user_id=user.id,
        submitted_at=now,
        materials=[m.model_dump(exclude_none=True) for m in payload.materials],
        review_status="pending",
    )
    db.add(verification)
    await db.flush()

    logger.info("coach_profile_applied", user_id=user.id, verification_id=verification.id)
    return CoachProfileRead.model_validate(profile).model_copy(
        update={
            "latest_verification_id": verification.id,
            "latest_review_status": "pending",
        }
    )


async def list_verifications_for_admin(
    db: AsyncSession,
    *,
    status: str = "pending",
    limit: int = 50,
) -> CoachVerificationListResponse:
    if status not in VALID_REVIEW_STATUSES:
        raise BadRequestError(code=40001, message="review_status 非法")
    limit = max(1, min(limit, 100))
    row = await db.execute(
        select(CoachVerification)
        .where(CoachVerification.review_status == status)
        .order_by(CoachVerification.submitted_at.asc())
        .limit(limit)
    )
    items = [CoachVerificationRead.model_validate(v) for v in row.scalars().all()]
    return CoachVerificationListResponse(items=items, total=len(items))


async def review_verification(
    db: AsyncSession,
    *,
    admin: User,
    verification_id: str,
    payload: CoachVerificationReview,
) -> CoachVerificationRead:
    assert_admin(admin)
    verification = await db.get(CoachVerification, verification_id)
    if verification is None:
        raise NotFoundError(code=40406, message="审核记录不存在")
    if verification.review_status != "pending":
        raise BadRequestError(code=40903, message="该记录已审核")

    profile = await get_profile(db, user_id=verification.user_id)
    if profile is None:
        raise NotFoundError(code=40406, message="教练档案不存在")

    now = _now()
    verification.review_status = payload.decision
    verification.reviewer_user_id = admin.id
    verification.reviewed_at = now
    verification.review_notes = payload.notes

    if payload.decision == "approved":
        profile.status = "active"
        profile.approved_at = now
        profile.rejected_at = None
    elif payload.decision == "rejected":
        profile.status = "rejected"
        profile.rejected_at = now
    else:
        profile.status = "rejected"
        profile.rejected_at = now

    await db.flush()
    logger.info(
        "coach_verification_reviewed",
        verification_id=verification_id,
        decision=payload.decision,
        reviewer=admin.id,
    )
    return CoachVerificationRead.model_validate(verification)


def raise_if_rejected_profile(profile: CoachProfile | None) -> None:
    if profile is not None and profile.status == "rejected":
        raise CoachVerificationRejectedError()


__all__ = [
    "admin_user_ids",
    "apply_profile",
    "assert_active_coach",
    "assert_admin",
    "ensure_coach_module_enabled",
    "get_my_profile",
    "get_profile_brief",
    "is_active_coach",
    "is_seed_coach",
    "list_verifications_for_admin",
    "review_verification",
]
