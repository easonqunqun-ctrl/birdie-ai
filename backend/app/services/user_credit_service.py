"""M13-06 / M13-07 · 约球用户信用分."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import MeetupCreditTooLowError
from app.models.user import User

INITIAL_MEETUP_CREDIT_SCORE = 100
MIN_MEETUP_CREDIT_SCORE = 0
MAX_MEETUP_CREDIT_SCORE = 100


def clamp_credit_score(value: int) -> int:
    return max(MIN_MEETUP_CREDIT_SCORE, min(MAX_MEETUP_CREDIT_SCORE, value))


def get_meetup_credit_score(user: User) -> int:
    return clamp_credit_score(int(user.meetup_credit_score or INITIAL_MEETUP_CREDIT_SCORE))


def credit_delta_from_feedback(*, rating: int, tags: list[str]) -> int:
    """互评 → 信用分变动（对齐 M13-07 kickoff §3.3 + M13-06 评分基线）."""

    delta = 5 * (rating - 3)
    tag_set = {t.strip().lower() for t in tags if t}
    alias = {
        "守时": "on_time",
        "punctual": "on_time",
        "友好": "friendly",
        "教学耐心": "patient_teaching",
        "失约": "no_show",
        "言语不当": "rude",
        "verbal_abuse": "rude",
    }
    tag_bonus = {
        "on_time": 2,
        "friendly": 1,
        "patient_teaching": 2,
        "no_show": -10,
        "rude": -15,
        "late": -1,
    }
    for raw in tag_set:
        key = alias.get(raw, raw)
        delta += tag_bonus.get(key, 0)
    return max(-20, min(20, delta))


def apply_credit_delta(user: User, delta: int) -> int:
    new_score = clamp_credit_score(get_meetup_credit_score(user) + delta)
    user.meetup_credit_score = new_score
    return new_score


def assert_credit_allows_invite(user: User, *, min_score: int) -> None:
    score = get_meetup_credit_score(user)
    if score < min_score:
        raise MeetupCreditTooLowError(
            detail=f"current={score}, required={min_score}",
        )


async def apply_feedback_to_user_credit(
    db: AsyncSession,
    *,
    user_id: str,
    rating: int,
    tags: list[str],
) -> int:
    user = await db.get(User, user_id)
    if user is None:
        return INITIAL_MEETUP_CREDIT_SCORE
    delta = credit_delta_from_feedback(rating=rating, tags=tags)
    score = apply_credit_delta(user, delta)
    await db.flush()
    return score


__all__ = [
    "INITIAL_MEETUP_CREDIT_SCORE",
    "apply_credit_delta",
    "apply_feedback_to_user_credit",
    "assert_credit_allows_invite",
    "clamp_credit_score",
    "credit_delta_from_feedback",
    "get_meetup_credit_score",
]
