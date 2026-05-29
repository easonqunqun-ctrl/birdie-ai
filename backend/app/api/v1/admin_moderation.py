"""M8-08 · 内容审核 Admin API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.moderation import (
    ModerationQueueItemRead,
    ModerationQueueListResponse,
    ModerationQueueReviewRequest,
)
from app.services import content_moderation_service as mod_svc

router = APIRouter()


@router.get(
    "/moderation/queue",
    summary="待人工审核队列（M8-08 Admin）",
    response_model=APIResponse[ModerationQueueListResponse],
)
async def list_moderation_queue(
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await mod_svc.list_pending_for_admin(db, admin=user, limit=limit)
    return ok(data)


@router.post(
    "/moderation/queue/{queue_id}/review",
    summary="人工审核处理（M8-08 Admin）",
    response_model=APIResponse[ModerationQueueItemRead],
)
async def review_moderation_queue_item(
    queue_id: str,
    payload: ModerationQueueReviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await mod_svc.review_queue_item(
        db, admin=user, queue_id=queue_id, payload=payload
    )
    await db.commit()
    return ok(data)
