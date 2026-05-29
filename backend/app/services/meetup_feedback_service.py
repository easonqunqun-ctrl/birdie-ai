"""M13-07 · 约球互评 + 24h 隔离 + 信用分联动."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.meetup import MeetupFeedback, MeetupInvitation
from app.schemas.meetup import FeedbackRead, MeetupFeedbackSubmit
from app.services import user_credit_service as credit_svc

logger = get_logger("meetup_feedback")

FEEDBACK_OPEN_HOURS = 24
PEER_VISIBILITY_HOURS = 24

TAG_ALIASES: dict[str, str] = {
    "守时": "on_time",
    "punctual": "on_time",
    "on_time": "on_time",
    "友好": "friendly",
    "friendly": "friendly",
    "教学耐心": "patient_teaching",
    "patient_teaching": "patient_teaching",
    "失约": "no_show",
    "no_show": "no_show",
    "言语不当": "rude",
    "rude": "rude",
    "verbal_abuse": "rude",
    "late": "late",
}

TAG_CREDIT_BONUS: dict[str, int] = {
    "on_time": 2,
    "friendly": 1,
    "patient_teaching": 2,
    "no_show": -10,
    "rude": -15,
    "late": -1,
}

VALID_CANONICAL_TAGS = frozenset(TAG_CREDIT_BONUS.keys())


def normalize_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        key = TAG_ALIASES.get(raw.strip().lower(), raw.strip().lower())
        if key not in VALID_CANONICAL_TAGS or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def calculate_feedback_credit_delta(*, rating: int, tags: list[str]) -> Decimal:
    """单条互评快照 delta（与 ``user_credit_service`` 用户总分公式对齐）."""

    delta_int = credit_svc.credit_delta_from_feedback(
        rating=rating, tags=normalize_tags(tags)
    )
    return Decimal(str(delta_int))


def _feedback_window_opens(inv: MeetupInvitation) -> datetime | None:
    if inv.accepted_at is None:
        return None
    return inv.accepted_at + timedelta(hours=FEEDBACK_OPEN_HOURS)


def _peer_visible_at(my_feedback: MeetupFeedback) -> datetime:
    return my_feedback.created_at + timedelta(hours=PEER_VISIBILITY_HOURS)


def _to_read(fb: MeetupFeedback) -> FeedbackRead:
    return FeedbackRead.model_validate(fb)


async def submit_feedback(
    db: AsyncSession, *, reviewer_user_id: str, payload: MeetupFeedbackSubmit
) -> MeetupFeedback:
    inv = await db.get(MeetupInvitation, payload.invitation_id)
    if inv is None:
        raise NotFoundError(code=40406, message="邀请不存在")
    if inv.status != "accepted":
        raise BadRequestError(
            code=40903,
            message="只能对已接受的约球互评",
            detail=inv.status,
        )
    if reviewer_user_id not in {inv.inviter_user_id, inv.invitee_user_id}:
        raise ForbiddenError(code=40330, message="非约球当事人无法评价")

    opens_at = _feedback_window_opens(inv)
    now = datetime.now(UTC)
    if opens_at is None or now < opens_at:
        raise BadRequestError(
            code=40904,
            message="约球结束后 24 小时才可评价",
        )

    reviewee_user_id = (
        inv.invitee_user_id
        if reviewer_user_id == inv.inviter_user_id
        else inv.inviter_user_id
    )

    tags = normalize_tags(list(payload.tags))
    if len(tags) > 8:
        raise BadRequestError(code=40001, message="标签最多 8 个")

    delta = calculate_feedback_credit_delta(rating=payload.rating, tags=tags)
    fb = MeetupFeedback(
        id=new_id("mfb"),
        invitation_id=inv.id,
        reviewer_user_id=reviewer_user_id,
        reviewee_user_id=reviewee_user_id,
        rating=payload.rating,
        tags=tags,
        credit_delta=delta,
        comment=payload.comment,
        is_visible=True,
    )
    db.add(fb)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ConflictError(
            code=40904,
            message="该约球你已评价过",
        ) from exc

    await credit_svc.apply_feedback_to_user_credit(
        db,
        user_id=reviewee_user_id,
        rating=payload.rating,
        tags=tags,
    )

    if "rude" in tags:
        logger.warning(
            "meetup_feedback_risk_alert",
            invitation_id=inv.id,
            reviewer_user_id=reviewer_user_id,
            reviewee_user_id=reviewee_user_id,
            tags=tags,
        )

    logger.info(
        "meetup_feedback_submitted",
        feedback_id=fb.id,
        invitation_id=inv.id,
        reviewer=reviewer_user_id,
        reviewee=reviewee_user_id,
        rating=payload.rating,
        credit_delta=str(delta),
    )
    return fb


async def list_feedbacks_for_invitation(
    db: AsyncSession,
    *,
    viewer_user_id: str,
    invitation_id: str,
) -> list[FeedbackRead]:
    inv = await db.get(MeetupInvitation, invitation_id)
    if inv is None:
        raise NotFoundError(code=40406, message="邀请不存在")
    if viewer_user_id not in {inv.inviter_user_id, inv.invitee_user_id}:
        raise ForbiddenError(code=40330, message="非约球当事人无法查看互评")

    rows = await db.execute(
        select(MeetupFeedback)
        .where(MeetupFeedback.invitation_id == invitation_id)
        .order_by(MeetupFeedback.created_at.asc())
    )
    all_fb = list(rows.scalars().all())
    mine = next((f for f in all_fb if f.reviewer_user_id == viewer_user_id), None)
    peer = next((f for f in all_fb if f.reviewer_user_id != viewer_user_id), None)

    out: list[FeedbackRead] = []
    if mine is not None:
        out.append(_to_read(mine))

    if (
        peer is not None
        and mine is not None
        and datetime.now(UTC) >= _peer_visible_at(mine)
    ):
        out.append(_to_read(peer))
    return out


async def list_my_feedbacks(
    db: AsyncSession, *, user_id: str, limit: int = 50
) -> list[FeedbackRead]:
    limit = max(1, min(limit, 100))
    rows = await db.execute(
        select(MeetupFeedback)
        .where(
            (MeetupFeedback.reviewer_user_id == user_id)
            | (MeetupFeedback.reviewee_user_id == user_id)
        )
        .order_by(MeetupFeedback.created_at.desc())
        .limit(limit)
    )
    return [_to_read(f) for f in rows.scalars().all()]


async def get_feedback_eligibility(
    db: AsyncSession, *, user_id: str, invitation_id: str
) -> dict:
    """客户端 gate：是否可评 / 是否已评 / 何时可见对方评分."""

    inv = await db.get(MeetupInvitation, invitation_id)
    if inv is None:
        raise NotFoundError(code=40406, message="邀请不存在")
    if user_id not in {inv.inviter_user_id, inv.invitee_user_id}:
        raise ForbiddenError(code=40330, message="非约球当事人")

    opens_at = _feedback_window_opens(inv)
    now = datetime.now(UTC)
    row = await db.execute(
        select(MeetupFeedback).where(
            MeetupFeedback.invitation_id == invitation_id,
            MeetupFeedback.reviewer_user_id == user_id,
        )
    )
    mine = row.scalar_one_or_none()
    peer_row = await db.execute(
        select(MeetupFeedback).where(
            MeetupFeedback.invitation_id == invitation_id,
            MeetupFeedback.reviewer_user_id != user_id,
        )
    )
    peer = peer_row.scalar_one_or_none()

    peer_visible = False
    if mine is not None and peer is not None:
        peer_visible = now >= _peer_visible_at(mine)

    return {
        "can_submit": (
            inv.status == "accepted"
            and opens_at is not None
            and now >= opens_at
            and mine is None
        ),
        "opens_at": opens_at.isoformat() if opens_at else None,
        "has_submitted": mine is not None,
        "peer_visible": peer_visible,
    }


__all__ = [
    "FEEDBACK_OPEN_HOURS",
    "PEER_VISIBILITY_HOURS",
    "calculate_feedback_credit_delta",
    "get_feedback_eligibility",
    "list_feedbacks_for_invitation",
    "list_my_feedbacks",
    "normalize_tags",
    "submit_feedback",
]
