"""M8-08 · 内容审核 Admin schema."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ModerationReviewActionLiteral = Literal["approve", "reject"]


class ModerationQueueItemRead(BaseModel):
    id: str
    target_table: str
    target_id: str
    media_type: str
    media_url: str | None = None
    text_snapshot: str | None = None
    ai_risk_label: str | None = None
    ai_risk_score: float | None = None
    ai_decision: str | None = None
    reviewer_user_id: str | None = None
    reviewer_action: str | None = None
    reviewer_note: str | None = None
    reviewed_at: datetime | None = None
    sla_deadline_at: datetime
    created_at: datetime


class ModerationQueueListResponse(BaseModel):
    items: list[ModerationQueueItemRead]
    total: int


class ModerationQueueReviewRequest(BaseModel):
    action: ModerationReviewActionLiteral
    note: str | None = Field(default=None, max_length=500)
