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
    # M13-02：地理坐标可选；同时为 None 时不会出现在 nearby
    latitude: Decimal | None = Field(None, ge=-90, le=90)
    longitude: Decimal | None = Field(None, ge=-180, le=180)

    model_config = ConfigDict(extra="forbid")


class VenueRead(BaseModel):
    id: str
    city: str
    name: str
    venue_type: VenueTypeLiteral
    address: str | None = None
    source: VenueSourceLiteral
    status: VenueStatusLiteral
    latitude: Decimal | None = None
    longitude: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class VenueNearbyItem(BaseModel):
    """GET /v1/venues/nearby 列表元素：venue 详情 + 距离（km）."""

    id: str
    city: str
    name: str
    venue_type: VenueTypeLiteral
    address: str | None = None
    source: VenueSourceLiteral
    status: VenueStatusLiteral
    latitude: Decimal
    longitude: Decimal
    distance_km: float

    model_config = ConfigDict(from_attributes=True)


class VenueNearbyResponse(BaseModel):
    """GET /v1/venues/nearby 响应体."""

    items: list[VenueNearbyItem]
    total: int
    # 回显请求参数，便于客户端调试 / 日志
    center_latitude: float
    center_longitude: float
    radius_km: float


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
    """M13-03：邀请列表 / 详情用响应；contact_payload 仅 accepted 后非空."""

    id: str
    inviter_user_id: str
    invitee_user_id: str
    venue_id: str | None = None
    proposed_time: datetime | None = None
    expires_at: datetime | None = None
    status: InvitationStatusLiteral
    accepted_at: datetime | None = None
    # contact_payload 只对当事人可见；当前实现简单粗暴：accepted 后返；
    # M13-04 会引入更细致的"只对 inviter / invitee 显示"逻辑
    contact_payload: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvitationListResponse(BaseModel):
    """GET /v1/users/me/meetup-invitations 响应体."""

    items: list[InvitationRead]
    total: int
    # 回显请求过滤参数（便于客户端 debug + 翻页时维持上下文）
    role: str
    status: str | None = None


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
    "InvitationListResponse",
    "InvitationRead",
    "InvitationStatusLiteral",
    "ParticipationStatusLiteral",
    "VenueCreate",
    "VenueNearbyItem",
    "VenueNearbyResponse",
    "VenueRead",
    "VenueSourceLiteral",
    "VenueStatusLiteral",
    "VenueTypeLiteral",
]
