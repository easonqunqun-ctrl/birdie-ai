"""M8-03 · 教练-学员绑定 schema."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CoachStudentStatus = Literal["pending", "active", "paused", "ended"]

VISIBILITY_FIELD_KEYS = (
    "handicap",
    "body",
    "injuries",
    "goals",
    "training_preference",
    "frequent_venues",
)

DEFAULT_VISIBILITY_PAYLOAD: dict[str, bool] = {k: False for k in VISIBILITY_FIELD_KEYS}


class CoachStudentInviteRequest(BaseModel):
    student_user_id: str | None = Field(default=None, max_length=32)
    invite_code: str | None = Field(default=None, max_length=8)
    message: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class CoachStudentVisibilityUpdate(BaseModel):
    handicap: bool | None = None
    body: bool | None = None
    injuries: bool | None = None
    goals: bool | None = None
    training_preference: bool | None = None
    frequent_venues: bool | None = None

    model_config = ConfigDict(extra="forbid")


class CoachStudentUserBrief(BaseModel):
    user_id: str
    nickname: str | None = None
    display_name: str | None = None


class CoachStudentRelationRead(BaseModel):
    id: str
    coach_user_id: str
    student_user_id: str
    status: CoachStudentStatus
    visibility_payload: dict[str, bool]
    invited_at: datetime
    invite_message: str | None = None
    accepted_at: datetime | None = None
    ended_at: datetime | None = None
    coach: CoachStudentUserBrief | None = None
    student: CoachStudentUserBrief | None = None


class CoachStudentListResponse(BaseModel):
    items: list[CoachStudentRelationRead]
    total: int


class StudentCoachOverviewResponse(BaseModel):
    pending: list[CoachStudentRelationRead] = Field(default_factory=list)
    active: CoachStudentRelationRead | None = None
    paused: CoachStudentRelationRead | None = None


class CoachStudentSharedFieldResponse(BaseModel):
    field: str
    visible: bool
    value: object | None = None


__all__ = [
    "DEFAULT_VISIBILITY_PAYLOAD",
    "VISIBILITY_FIELD_KEYS",
    "CoachStudentInviteRequest",
    "CoachStudentListResponse",
    "CoachStudentRelationRead",
    "CoachStudentSharedFieldResponse",
    "CoachStudentStatus",
    "CoachStudentUserBrief",
    "CoachStudentVisibilityUpdate",
    "StudentCoachOverviewResponse",
]
