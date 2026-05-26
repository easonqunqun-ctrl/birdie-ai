"""二期 M12 球手对比库 Pydantic schema（对齐 docs/23 §8.1）.

只覆盖 service / 路由侧需要的最小写入 / 读取面；UI 形态字段由 M12-03 / M12-05 PR
再细化。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LicenseStatusLiteral = Literal["public_clip", "authorized", "partnership"]
HandednessLiteral = Literal["right", "left"]
CameraAngleLiteral = Literal["face_on", "down_the_line"]
AnnotationTypeLiteral = Literal["text", "voice", "sketch"]


class ProPlayerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    name_en: str | None = Field(None, max_length=80)
    nationality: str | None = Field(None, min_length=3, max_length=3)
    handedness: HandednessLiteral = "right"
    height_cm: int | None = Field(None, ge=140, le=230)
    avatar_url: str | None = Field(None, max_length=512)
    short_bio: str | None = None
    license_status: LicenseStatusLiteral = "public_clip"
    is_active: bool = True
    sort_order: int = Field(0, ge=0, le=9999)

    model_config = ConfigDict(extra="forbid")


class ProPlayerRead(BaseModel):
    id: str
    name: str
    name_en: str | None = None
    nationality: str | None = None
    handedness: HandednessLiteral
    height_cm: int | None = None
    avatar_url: str | None = None
    short_bio: str | None = None
    license_status: LicenseStatusLiteral
    is_active: bool
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class ProSwingClipCreate(BaseModel):
    pro_player_id: str = Field(..., max_length=32)
    club_type: str = Field(..., min_length=1, max_length=20)
    camera_angle: CameraAngleLiteral
    video_url: str = Field(..., min_length=1, max_length=512)
    thumbnail_url: str | None = Field(None, max_length=512)
    duration_ms: int | None = Field(None, ge=500, le=60000)
    fps: int | None = Field(None, ge=24, le=240)
    overall_score: int | None = Field(None, ge=0, le=100)
    engine_version: str = Field("v1", max_length=20)
    features_snapshot: dict = Field(default_factory=dict)
    phase_timestamps: dict | None = None
    license_status: LicenseStatusLiteral
    source_credit: str = Field(..., min_length=1, max_length=200)
    source_url: str = Field(..., min_length=1, max_length=512)
    captured_year: int | None = Field(None, ge=1950, le=2099)
    description: str | None = None
    is_published: bool = False

    model_config = ConfigDict(extra="forbid")


class ProSwingClipRead(BaseModel):
    id: str
    pro_player_id: str
    club_type: str
    camera_angle: CameraAngleLiteral
    video_url: str
    thumbnail_url: str | None = None
    duration_ms: int | None = None
    fps: int | None = None
    overall_score: int | None = None
    engine_version: str
    features_snapshot: dict
    license_status: LicenseStatusLiteral
    source_credit: str
    source_url: str
    captured_year: int | None = None
    is_published: bool

    model_config = ConfigDict(from_attributes=True)


class ProClipAnnotationCreate(BaseModel):
    clip_id: str = Field(..., max_length=32)
    author_user_id: str | None = Field(None, max_length=32)
    annotation_type: AnnotationTypeLiteral
    content: str | None = None
    time_marker_ms: int | None = Field(None, ge=0, le=600000)
    is_visible: bool = True

    model_config = ConfigDict(extra="forbid")


class ProTopicCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    title: str = Field(..., min_length=1, max_length=100)
    subtitle: str | None = Field(None, max_length=200)
    banner_url: str | None = Field(None, max_length=512)
    summary: str | None = None
    clip_ids: list[str] = Field(default_factory=list, max_length=50)
    week_starts_at: date | None = None
    is_published: bool = False

    model_config = ConfigDict(extra="forbid")


class UserProMatchCreate(BaseModel):
    analysis_id: str = Field(..., max_length=32)
    matched_clip_id: str = Field(..., max_length=32)
    match_score: Decimal = Field(..., ge=0, le=100)
    match_details: dict = Field(default_factory=dict)


class UserProMatchRead(BaseModel):
    id: str
    user_id: str
    analysis_id: str
    matched_clip_id: str
    match_score: Decimal
    match_details: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "AnnotationTypeLiteral",
    "CameraAngleLiteral",
    "HandednessLiteral",
    "LicenseStatusLiteral",
    "ProClipAnnotationCreate",
    "ProPlayerCreate",
    "ProPlayerRead",
    "ProSwingClipCreate",
    "ProSwingClipRead",
    "ProTopicCreate",
    "UserProMatchCreate",
    "UserProMatchRead",
]
