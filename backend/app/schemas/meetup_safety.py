"""M13-09 · 约球合规 Pydantic schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

GenderPreferenceLiteral = Literal["any", "same", "coach_only"]


class MeetupSafetyStatus(BaseModel):
    meetup_tos_accepted_at: str | None = None
    gender_preference: GenderPreferenceLiteral
    coach_spectator_optin: bool = False
    identity_eligible: bool
    phone_verified: bool
    age_years: int | None = None
    can_use_meetup: bool
    tos_text_version: str = "m13-v0.1"


class MeetupGenderPreferenceUpdate(BaseModel):
    gender_preference: GenderPreferenceLiteral

    model_config = ConfigDict(extra="forbid")


class MeetupSpectatorOptinUpdate(BaseModel):
    coach_spectator_optin: bool

    model_config = ConfigDict(extra="forbid")


class MeetupTosAccept(BaseModel):
    gender_preference: GenderPreferenceLiteral | None = None

    model_config = ConfigDict(extra="forbid")


class MeetupTosContent(BaseModel):
    version: str = "m13-v0.1"
    title: str = "约球功能服务须知"
    body: str
    disclaimer: str
