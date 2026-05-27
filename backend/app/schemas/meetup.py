"""二期 M13 约球 Pydantic schema（对齐 docs/23 §9.1）.

只覆盖 service / 路由侧最小写入 / 读取面；M13-03 ~ M13-10 PR 再按需扩展。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VenueTypeLiteral = Literal["indoor_range", "outdoor_range", "simulator_lounge", "golf_course"]
VenueSourceLiteral = Literal["ugc", "verified"]
VenueStatusLiteral = Literal["active", "flagged", "closed"]
InvitationStatusLiteral = Literal["pending", "accepted", "declined", "expired", "cancelled"]
EventStatusLiteral = Literal["draft", "open", "closed", "cancelled", "completed"]
ParticipationStatusLiteral = Literal[
    "signed_up", "checked_in", "completed", "no_show", "cancelled"
]


class VenueCreate(BaseModel):
    city: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=128)
    venue_type: VenueTypeLiteral
    address: str | None = None
    source: VenueSourceLiteral = "ugc"

    model_config = ConfigDict(extra="forbid")


class VenueRead(BaseModel):
    id: str
    city: str
    name: str
    venue_type: VenueTypeLiteral
    address: str | None = None
    source: VenueSourceLiteral
    status: VenueStatusLiteral

    model_config = ConfigDict(from_attributes=True)


class InvitationCreate(BaseModel):
    invitee_user_id: str = Field(..., max_length=32)
    venue_id: str | None = Field(None, max_length=32)
    proposed_time: datetime | None = None
    expires_at: datetime | None = None
    message: str | None = Field(None, max_length=200)

    model_config = ConfigDict(extra="forbid")


class InvitationAcceptPayload(BaseModel):
    """``contact_payload`` 显式公约：仅允许 ``note`` 与会面相关字段."""

    note: str | None = Field(None, max_length=200)
    meet_at: str | None = Field(None, max_length=80)  # 自由文本（"8 点门口"）

    model_config = ConfigDict(extra="forbid")


class InvitationRead(BaseModel):
    """M13-03 / M13-04：邀请响应；contact_payload 仅当事人可见.

    NOTE：本 schema 同时在 M13-03 (#113) 与 M13-04 (#114) PR 中引入；
    merge 时择一保留即可（两份内容完全一致）。
    """

    id: str
    inviter_user_id: str
    invitee_user_id: str
    venue_id: str | None = None
    proposed_time: datetime | None = None
    expires_at: datetime | None = None
    status: InvitationStatusLiteral
    accepted_at: datetime | None = None
    contact_payload: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackCreate(BaseModel):
    invitation_id: str = Field(..., max_length=32)
    reviewee_user_id: str = Field(..., max_length=32)
    rating: int = Field(..., ge=1, le=5)
    tags: list[str] = Field(default_factory=list, max_length=8)
    comment: str | None = Field(None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class FeedbackRead(BaseModel):
    id: str
    invitation_id: str
    reviewer_user_id: str
    reviewee_user_id: str
    rating: int
    tags: list[str]
    credit_delta: Decimal
    comment: str | None = None
    is_visible: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventCreate(BaseModel):
    venue_id: str | None = Field(None, max_length=32)
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    template_code: str | None = Field(None, max_length=40)
    scheduled_at: datetime | None = None
    capacity: int | None = Field(None, ge=1, le=200)
    badge_template_code: str | None = Field(None, max_length=40)
    rules_payload: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class EventRead(BaseModel):
    id: str
    organizer_user_id: str
    venue_id: str | None = None
    title: str
    template_code: str | None = None
    scheduled_at: datetime | None = None
    capacity: int | None = None
    status: EventStatusLiteral
    badge_template_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "EventCreate",
    "EventRead",
    "EventStatusLiteral",
    "FeedbackCreate",
    "FeedbackRead",
    "InvitationAcceptPayload",
    "InvitationCreate",
    "InvitationRead",
    "InvitationStatusLiteral",
    "ParticipationStatusLiteral",
    "VenueCreate",
    "VenueRead",
    "VenueSourceLiteral",
    "VenueStatusLiteral",
    "VenueTypeLiteral",
]
