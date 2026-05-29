"""M8-01 · 教练档案 / 资质审核 Pydantic schema."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CoachLevelLiteral = Literal["pga", "china_pga", "regional", "club_pro"]
CoachProfileStatusLiteral = Literal["pending", "active", "rejected", "paused"]
CoachReviewStatusLiteral = Literal["pending", "approved", "rejected", "need_more"]
CoachReviewDecisionLiteral = Literal["approved", "rejected", "need_more"]


class CoachCertificationItem(BaseModel):
    type: str = Field(..., min_length=1, max_length=40)
    number: str | None = Field(None, max_length=64)
    issued_at: str | None = Field(None, max_length=32)
    country: str | None = Field(None, max_length=32)
    association: str | None = Field(None, max_length=64)
    venue: str | None = Field(None, max_length=128)

    model_config = ConfigDict(extra="forbid")


class CoachMaterialItem(BaseModel):
    type: str = Field(..., min_length=1, max_length=40)
    object_key: str = Field(..., min_length=1, max_length=512)
    uploaded_at: str | None = None
    sha256: str | None = Field(None, max_length=64)

    model_config = ConfigDict(extra="forbid")


class CoachProfileApply(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=60)
    level: CoachLevelLiteral
    bio: str | None = Field(None, max_length=2000)
    avatar_url: str | None = Field(None, max_length=512)
    specialties: list[str] = Field(default_factory=list, max_length=12)
    service_cities: list[str] = Field(default_factory=list, max_length=12)
    certifications: list[CoachCertificationItem] = Field(default_factory=list, max_length=8)
    materials: list[CoachMaterialItem] = Field(default_factory=list, max_length=8)

    model_config = ConfigDict(extra="forbid")


class CoachProfileBrief(BaseModel):
    status: CoachProfileStatusLiteral
    display_name: str
    level: CoachLevelLiteral
    applied_at: datetime
    approved_at: datetime | None = None
    rejected_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CoachProfileRead(CoachProfileBrief):
    user_id: str
    avatar_url: str | None = None
    bio: str | None = None
    specialties: list[str] = Field(default_factory=list)
    service_cities: list[str] = Field(default_factory=list)
    certifications: list[dict] = Field(default_factory=list)
    latest_verification_id: str | None = None
    latest_review_status: CoachReviewStatusLiteral | None = None

    model_config = ConfigDict(from_attributes=True)


class CoachVerificationRead(BaseModel):
    id: str
    user_id: str
    submitted_at: datetime
    materials: list[dict] = Field(default_factory=list)
    review_status: CoachReviewStatusLiteral
    reviewed_at: datetime | None = None
    review_notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CoachVerificationReview(BaseModel):
    decision: CoachReviewDecisionLiteral
    notes: str | None = Field(None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class CoachVerificationListResponse(BaseModel):
    items: list[CoachVerificationRead]
    total: int


__all__ = [
    "CoachCertificationItem",
    "CoachLevelLiteral",
    "CoachMaterialItem",
    "CoachProfileApply",
    "CoachProfileBrief",
    "CoachProfileRead",
    "CoachProfileStatusLiteral",
    "CoachReviewDecisionLiteral",
    "CoachReviewStatusLiteral",
    "CoachVerificationListResponse",
    "CoachVerificationRead",
    "CoachVerificationReview",
]
