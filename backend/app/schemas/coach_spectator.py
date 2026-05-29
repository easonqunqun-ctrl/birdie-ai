"""M13-10 · 教练旁观约球 Pydantic schema."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.meetup import InvitationStatusLiteral

StudentRoleLiteral = Literal["inviter", "invitee"]


class CoachSpectatorInvitationRead(BaseModel):
    id: str
    student_role: StudentRoleLiteral
    peer_user_id: str | None = None
    peer_redacted: bool = True
    venue_id: str | None = None
    proposed_time: datetime | None = None
    expires_at: datetime | None = None
    status: InvitationStatusLiteral
    accepted_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CoachStudentMeetupsResponse(BaseModel):
    items: list[CoachSpectatorInvitationRead]
    total: int
    page: int
    page_size: int
    student_user_id: str


class CoachSpectatorOptinUpdate(BaseModel):
    coach_spectator_optin: bool

    model_config = ConfigDict(extra="forbid")


class CoachSpectatorOptinStatus(BaseModel):
    coach_spectator_optin: bool


__all__ = [
    "CoachSpectatorInvitationRead",
    "CoachSpectatorOptinStatus",
    "CoachSpectatorOptinUpdate",
    "CoachStudentMeetupsResponse",
    "StudentRoleLiteral",
]
