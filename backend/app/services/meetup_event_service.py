"""M13-08 · 自助小型挑战赛 service（对齐 kickoff §3）.

职责
----
- 3 种 rule_template 创建 / 列表 / 报名 / 自报成绩 / 排行 / 完赛荣誉徽章
- **严禁** reward_cash / reward_item（红线 R6）；徽章仅写入 ``moderation_payload``

刻意不做
--------
- M8-08 成绩单图人工审核队列（``score_image_url`` 先落库 ``review_status=pending``）
- 高级排名 / 战队
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cmp_to_key

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.meetup import EventParticipation, SelfOrganizedEvent
from app.schemas.meetup import EventCreate, EventScoreSubmit
from app.services.meetup_event_rules import (
    EVENT_RULE_TEMPLATES,
    compare_scores,
    validate_score_for_template,
)

DEFAULT_EVENT_CAPACITY = 8
ACTIVE_PARTICIPATION_STATUSES = frozenset({"signed_up", "checked_in", "completed"})

logger = get_logger("meetup_event")


def _now() -> datetime:
    return datetime.now(UTC)


def _template_or_raise(code: str | None) -> str:
    if not code or code not in EVENT_RULE_TEMPLATES:
        raise BadRequestError(
            code=40052,
            message="template_code 必须是 putting_contest / distance_contest / overall_score",
        )
    return code


async def create_event(
    db: AsyncSession, *, organizer_user_id: str, payload: EventCreate
) -> SelfOrganizedEvent:
    template_code = _template_or_raise(payload.template_code)
    tpl = EVENT_RULE_TEMPLATES[template_code]
    capacity = payload.capacity if payload.capacity is not None else tpl.default_capacity
    rules = dict(tpl.rules_payload)
    if payload.rules_payload:
        rules.update(payload.rules_payload)

    e = SelfOrganizedEvent(
        id=new_id("soe"),
        organizer_user_id=organizer_user_id,
        venue_id=payload.venue_id,
        title=payload.title.strip(),
        description=payload.description,
        template_code=template_code,
        scheduled_at=payload.scheduled_at,
        capacity=capacity,
        status="open",
        badge_template_code=payload.badge_template_code or f"honor_{template_code}",
        rules_payload=rules,
    )
    db.add(e)
    await db.flush()
    logger.info(
        "meetup_event_created",
        event_id=e.id,
        organizer=organizer_user_id,
        template=template_code,
    )
    return e


async def list_events(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = "open",
) -> tuple[list[SelfOrganizedEvent], int]:
    page = max(1, page)
    page_size = max(1, min(page_size, 50))
    stmt = select(SelfOrganizedEvent)
    if status:
        stmt = stmt.where(SelfOrganizedEvent.status == status)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await db.execute(count_stmt)).scalar_one())
    rows = await db.execute(
        stmt.order_by(SelfOrganizedEvent.scheduled_at.asc().nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.scalars().all()), total


async def get_event(db: AsyncSession, *, event_id: str) -> SelfOrganizedEvent:
    e = await db.get(SelfOrganizedEvent, event_id)
    if e is None:
        raise NotFoundError(code=40406, message="活动不存在")
    return e


async def _count_active_participants(db: AsyncSession, event_id: str) -> int:
    rows = await db.execute(
        select(func.count())
        .select_from(EventParticipation)
        .where(
            EventParticipation.event_id == event_id,
            EventParticipation.status.in_(tuple(ACTIVE_PARTICIPATION_STATUSES)),
        )
    )
    return int(rows.scalar_one())


async def join_event(
    db: AsyncSession, *, event_id: str, user_id: str
) -> EventParticipation:
    e = await get_event(db, event_id=event_id)
    if e.status != "open":
        raise BadRequestError(code=40903, message="活动未开放报名", detail=e.status)

    existing = await db.execute(
        select(EventParticipation).where(
            EventParticipation.event_id == event_id,
            EventParticipation.user_id == user_id,
            EventParticipation.status != "cancelled",
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise BadRequestError(code=40905, message="你已报名该活动")

    cap = e.capacity or DEFAULT_EVENT_CAPACITY
    if await _count_active_participants(db, event_id) >= cap:
        raise BadRequestError(code=42910, message="活动报名已满")

    p = EventParticipation(
        id=new_id("evp"),
        event_id=event_id,
        user_id=user_id,
        status="signed_up",
    )
    db.add(p)
    await db.flush()
    return p


async def submit_score(
    db: AsyncSession,
    *,
    event_id: str,
    user_id: str,
    payload: EventScoreSubmit,
) -> EventParticipation:
    e = await get_event(db, event_id=event_id)
    if e.status not in {"open", "closed", "completed"}:
        raise BadRequestError(code=40903, message="活动当前不可提交成绩")

    row = await db.execute(
        select(EventParticipation).where(
            EventParticipation.event_id == event_id,
            EventParticipation.user_id == user_id,
            EventParticipation.status.in_(tuple(ACTIVE_PARTICIPATION_STATUSES)),
        )
    )
    p = row.scalar_one_or_none()
    if p is None:
        raise ForbiddenError(code=40301, message="仅报名用户可提交成绩")

    existing = dict(p.score_payload or {})
    if existing.get("review_status") in {"pending", "approved"}:
        raise BadRequestError(code=40905, message="成绩已提交，不可重复提交")

    try:
        validate_score_for_template(e.template_code, payload.self_reported_score)
    except ValueError as exc:
        raise BadRequestError(code=40052, message=str(exc)) from exc

    review_status = "pending" if payload.score_image_url else "approved"
    p.score_payload = {
        "self_reported_score": payload.self_reported_score,
        "score_image_url": payload.score_image_url,
        "review_status": review_status,
        "submitted_at": _now().isoformat(),
    }
    if review_status == "approved":
        p.status = "completed"
        p.completed_at = _now()
        await _award_event_badge(db, event=e, user_id=user_id)
    await db.flush()
    return p


async def _award_event_badge(
    db: AsyncSession, *, event: SelfOrganizedEvent, user_id: str
) -> None:
    """写入 honor-only 徽章元数据（无现金 / 实物字段）."""

    meta = dict(event.moderation_payload or {})
    badges = dict(meta.get("completion_badges") or {})
    if user_id in badges:
        return
    badges[user_id] = {
        "title": f"{event.title} · 完赛",
        "scope": "meetup_event",
        "event_id": event.id,
        "template_code": event.template_code,
        "honor_only": True,
        "awarded_at": _now().isoformat(),
    }
    meta["completion_badges"] = badges
    event.moderation_payload = meta


async def build_leaderboard(
    db: AsyncSession, *, event_id: str
) -> list[dict]:
    e = await get_event(db, event_id=event_id)
    rows = await db.execute(
        select(EventParticipation).where(
            EventParticipation.event_id == event_id,
            EventParticipation.status.in_(("signed_up", "checked_in", "completed")),
        )
    )
    ranked: list[dict] = []
    for p in rows.scalars().all():
        sp = dict(p.score_payload or {})
        if sp.get("review_status") != "approved":
            continue
        score = sp.get("self_reported_score")
        if score is None:
            continue
        ranked.append(
            {
                "user_id": p.user_id,
                "participation_id": p.id,
                "self_reported_score": score,
                "submitted_at": sp.get("submitted_at"),
            }
        )
    ranked.sort(
        key=cmp_to_key(
            lambda a, b: compare_scores(
                e.template_code, a["self_reported_score"], b["self_reported_score"]
            )
        )
    )
    for idx, item in enumerate(ranked, start=1):
        item["rank"] = idx
    return ranked


async def event_to_read_dict(
    db: AsyncSession, *, event: SelfOrganizedEvent, viewer_user_id: str | None = None
) -> dict:
    tpl = EVENT_RULE_TEMPLATES.get(event.template_code or "")
    participant_count = await _count_active_participants(db, event.id)
    badges = (event.moderation_payload or {}).get("completion_badges") or {}
    my_badge = badges.get(viewer_user_id) if viewer_user_id else None
    my_participation_status: str | None = None
    if viewer_user_id:
        prow = await db.execute(
            select(EventParticipation.status).where(
                EventParticipation.event_id == event.id,
                EventParticipation.user_id == viewer_user_id,
                EventParticipation.status != "cancelled",
            )
        )
        my_participation_status = prow.scalar_one_or_none()
    return {
        "id": event.id,
        "organizer_user_id": event.organizer_user_id,
        "venue_id": event.venue_id,
        "title": event.title,
        "description": event.description,
        "template_code": event.template_code,
        "template_label": tpl.label if tpl else None,
        "scheduled_at": event.scheduled_at,
        "capacity": event.capacity,
        "participant_count": participant_count,
        "status": event.status,
        "badge_template_code": event.badge_template_code,
        "rules_payload": event.rules_payload,
        "score_label": tpl.score_label if tpl else None,
        "my_completion_badge": my_badge,
        "my_participation_status": my_participation_status,
        "leaderboard": await build_leaderboard(db, event_id=event.id),
    }


__all__ = [
    "DEFAULT_EVENT_CAPACITY",
    "build_leaderboard",
    "create_event",
    "event_to_read_dict",
    "get_event",
    "join_event",
    "list_events",
    "submit_score",
]
