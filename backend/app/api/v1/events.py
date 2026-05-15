"""埋点 / 错误上报 API（W8-T5）。

端点
----
- `POST /v1/events` 批量事件上报（支持匿名）

设计取舍
--------
1. 允许匿名：`get_current_user_optional` 能拿到就带 user_id，拿不到就 user_id=None
   场景：App.onError 可能在未登录态也被触发
2. 接受部分失败：只要整体入参合法，某些事件名不在白名单 → 只计 `rejected`，
   不让一条脏数据拉挂整个批次
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.event import TrackBatchRequest, TrackBatchResponse
from app.services import event_service

router = APIRouter()


@router.post(
    "",
    summary="批量上报埋点 / 错误",
    response_model=APIResponse[TrackBatchResponse],
)
async def batch_track(
    payload: TrackBatchRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> APIResponse[TrackBatchResponse]:
    accepted, rejected = await event_service.insert_events(
        db,
        user_id=user.id if user else None,
        batch=[e.model_dump() for e in payload.events],
    )
    await db.commit()
    return ok(TrackBatchResponse(accepted=accepted, rejected=rejected))
