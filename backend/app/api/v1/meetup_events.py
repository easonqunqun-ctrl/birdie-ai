"""M13-08 · 自助挑战赛 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.meetup_guard import ensure_meetup_user_ready
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.meetup import (
    EventCreate,
    EventListResponse,
    EventRead,
    EventScoreSubmit,
    EventTemplateRead,
)
from app.services import meetup_event_service as event_svc
from app.services.meetup_event_rules import EVENT_RULE_TEMPLATES

router = APIRouter()


@router.get(
    "/events/templates",
    summary="挑战赛模板列表（M13-08）",
    response_model=APIResponse[list[EventTemplateRead]],
)
async def list_event_templates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_meetup_user_ready(db, user=user)
    items = [
        EventTemplateRead(
            code=t.code,
            label=t.label,
            description=t.description,
            default_capacity=t.default_capacity,
            score_label=t.score_label,
        )
        for t in EVENT_RULE_TEMPLATES.values()
    ]
    return ok(items)


@router.post(
    "/events",
    summary="创建挑战赛（M13-08）",
    response_model=APIResponse[EventRead],
)
async def create_meetup_event(
    payload: EventCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_meetup_user_ready(db, user=user)
    event = await event_svc.create_event(
        db, organizer_user_id=user.id, payload=payload
    )
    await db.commit()
    data = await event_svc.event_to_read_dict(
        db, event=event, viewer_user_id=user.id
    )
    return ok(EventRead.model_validate(data))


@router.get(
    "/events",
    summary="挑战赛列表（M13-08）",
    response_model=APIResponse[EventListResponse],
)
async def list_meetup_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    status: str | None = Query("open"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_meetup_user_ready(db, user=user)
    events, total = await event_svc.list_events(
        db, page=page, page_size=page_size, status=status
    )
    items: list[EventRead] = []
    for event in events:
        data = await event_svc.event_to_read_dict(
            db, event=event, viewer_user_id=user.id
        )
        items.append(EventRead.model_validate(data))
    return ok(
        EventListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/events/{event_id}",
    summary="挑战赛详情（M13-08）",
    response_model=APIResponse[EventRead],
)
async def get_meetup_event(
    event_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_meetup_user_ready(db, user=user)
    event = await event_svc.get_event(db, event_id=event_id)
    data = await event_svc.event_to_read_dict(
        db, event=event, viewer_user_id=user.id
    )
    return ok(EventRead.model_validate(data))


@router.post(
    "/events/{event_id}/join",
    summary="报名挑战赛（M13-08）",
    response_model=APIResponse[EventRead],
)
async def join_meetup_event(
    event_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_meetup_user_ready(db, user=user)
    await event_svc.join_event(db, event_id=event_id, user_id=user.id)
    await db.commit()
    event = await event_svc.get_event(db, event_id=event_id)
    data = await event_svc.event_to_read_dict(
        db, event=event, viewer_user_id=user.id
    )
    return ok(EventRead.model_validate(data))


@router.post(
    "/events/{event_id}/submit-score",
    summary="提交挑战赛成绩（M13-08）",
    response_model=APIResponse[EventRead],
)
async def submit_meetup_event_score(
    event_id: str,
    payload: EventScoreSubmit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_meetup_user_ready(db, user=user)
    await event_svc.submit_score(
        db, event_id=event_id, user_id=user.id, payload=payload
    )
    await db.commit()
    event = await event_svc.get_event(db, event_id=event_id)
    data = await event_svc.event_to_read_dict(
        db, event=event, viewer_user_id=user.id
    )
    return ok(EventRead.model_validate(data))
