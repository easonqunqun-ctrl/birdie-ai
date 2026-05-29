"""M13-09 · 约球合规：协议 / 实名 / 未成年 / 女性安全偏好."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    MeetupIdentityRequiredError,
    MeetupMinorBlockedError,
    MeetupTosRequiredError,
)
from app.core.logging import get_logger
from app.models.meetup import MIN_MEETUP_AGE
from app.models.user import User
from app.models.user_profile_v2 import UserProfileV2

GenderPreference = Literal["any", "same", "coach_only"]

MEETUP_TOS_KEY = "meetup_tos_accepted_at"
GENDER_PREFERENCE_KEY = "gender_preference"
VALID_GENDER_PREFERENCES: frozenset[str] = frozenset({"any", "same", "coach_only"})

logger = get_logger("meetup_safety")


def _now() -> datetime:
    return datetime.now(UTC)


def user_age_years(user: User, *, on_date: date | None = None) -> int | None:
    if user.birth_date is None:
        return None
    today = on_date or _now().date()
    years = today.year - user.birth_date.year
    if (today.month, today.day) < (user.birth_date.month, user.birth_date.day):
        years -= 1
    return years


def is_phone_verified(user: User) -> bool:
    return user.phone_verified_at is not None


def default_gender_preference(user: User) -> GenderPreference:
    if user.gender == "female":
        return "same"
    return "any"


def assert_identity_eligible(user: User) -> None:
    """14 岁以下拦截 + 实名手机号（M13-09 kickoff §3.2）."""

    if not is_phone_verified(user) or user.birth_date is None:
        raise MeetupIdentityRequiredError()
    age = user_age_years(user)
    if age is not None and age < MIN_MEETUP_AGE:
        raise MeetupMinorBlockedError()


async def _get_or_create_profile(db: AsyncSession, user_id: str) -> UserProfileV2:
    profile = await db.get(UserProfileV2, user_id)
    if profile is None:
        profile = UserProfileV2(user_id=user_id, privacy_payload={})
        db.add(profile)
        await db.flush()
    return profile


def _read_privacy(profile: UserProfileV2 | None) -> dict:
    return dict((profile.privacy_payload if profile else None) or {})


async def get_safety_status(db: AsyncSession, *, user: User) -> dict:
    profile = await db.get(UserProfileV2, user.id)
    payload = _read_privacy(profile)
    pref = payload.get(GENDER_PREFERENCE_KEY)
    if pref not in VALID_GENDER_PREFERENCES:
        pref = default_gender_preference(user)
    age = user_age_years(user)
    return {
        "meetup_tos_accepted_at": payload.get(MEETUP_TOS_KEY),
        "gender_preference": pref,
        "identity_eligible": _identity_eligible_soft(user),
        "phone_verified": is_phone_verified(user),
        "age_years": age,
        "can_use_meetup": _can_use_meetup(user, payload),
        "tos_text_version": "m13-v0.1",
    }


def _identity_eligible_soft(user: User) -> bool:
    age = user_age_years(user)
    if not is_phone_verified(user) or user.birth_date is None:
        return False
    return not (age is not None and age < MIN_MEETUP_AGE)


def _can_use_meetup(user: User, payload: dict) -> bool:
    if not _identity_eligible_soft(user):
        return False
    return bool(payload.get(MEETUP_TOS_KEY))


async def accept_meetup_tos(
    db: AsyncSession, *, user: User, gender_preference: GenderPreference | None = None
) -> dict:
    assert_identity_eligible(user)
    profile = await _get_or_create_profile(db, user.id)
    payload = _read_privacy(profile)
    payload[MEETUP_TOS_KEY] = _now().isoformat()
    pref = gender_preference or payload.get(GENDER_PREFERENCE_KEY)
    if pref not in VALID_GENDER_PREFERENCES:
        pref = default_gender_preference(user)
    payload[GENDER_PREFERENCE_KEY] = pref
    profile.privacy_payload = payload
    await db.flush()
    logger.info("meetup_tos_accepted", user_id=user.id)
    return await get_safety_status(db, user=user)


async def update_gender_preference(
    db: AsyncSession, *, user: User, preference: GenderPreference
) -> dict:
    if preference not in VALID_GENDER_PREFERENCES:
        from app.core.exceptions import BadRequestError

        raise BadRequestError(code=40052, message="gender_preference 非法")
    profile = await _get_or_create_profile(db, user.id)
    payload = _read_privacy(profile)
    payload[GENDER_PREFERENCE_KEY] = preference
    profile.privacy_payload = payload
    await db.flush()
    return await get_safety_status(db, user=user)


async def ensure_meetup_access(db: AsyncSession, *, user: User) -> None:
    """所有 M13 写 / 读端点调用：实名 + 协议."""

    if settings.MEETUP_MOCK_IDENTITY_VERIFIED and settings.WECHAT_MOCK_LOGIN:
        maybe_stamp_mock_identity(user)
    assert_identity_eligible(user)
    profile = await db.get(UserProfileV2, user.id)
    payload = _read_privacy(profile)
    if not payload.get(MEETUP_TOS_KEY):
        raise MeetupTosRequiredError()


def maybe_stamp_mock_identity(user: User) -> None:
    """mock 登录补齐成年实名，便于 CI / 本地联调."""

    changed = False
    if user.birth_date is None:
        user.birth_date = date(1990, 1, 1)
        changed = True
    if user.phone_verified_at is None:
        user.phone_verified_at = _now()
        changed = True
    if changed:
        logger.debug("meetup_mock_identity_stamped", user_id=user.id)


async def stamp_mock_identity(db: AsyncSession, *, user: User) -> User:
    maybe_stamp_mock_identity(user)
    await db.flush()
    return user


__all__ = [
    "GENDER_PREFERENCE_KEY",
    "MEETUP_TOS_KEY",
    "VALID_GENDER_PREFERENCES",
    "GenderPreference",
    "accept_meetup_tos",
    "assert_identity_eligible",
    "default_gender_preference",
    "ensure_meetup_access",
    "get_safety_status",
    "stamp_mock_identity",
    "update_gender_preference",
    "user_age_years",
]
