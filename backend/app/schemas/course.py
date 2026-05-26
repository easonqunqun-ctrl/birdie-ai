"""二期 M11 课程体系 Pydantic schema（对齐 docs/23 §7.1）.

只覆盖 service / 路由侧需要的最小写入 / 读取面；UI 形态字段由 M11-03 PR 再细化。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CourseStatusLiteral = Literal["not_started", "in_progress", "passed", "failed"]


class CourseCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    title: str = Field(..., min_length=1, max_length=100)
    subtitle: str | None = Field(None, max_length=200)
    cover_url: str | None = Field(None, max_length=512)
    stage: int = Field(..., ge=1, le=7)
    sort_order: int = 0
    is_member_only: bool = False
    description: str | None = None
    learning_objectives: list[str] = Field(default_factory=list, max_length=20)
    estimated_minutes: int = Field(60, ge=1, le=600)
    created_by_user_id: str | None = Field(None, max_length=32)

    model_config = ConfigDict(extra="forbid")


class CourseUpdate(BaseModel):
    title: str | None = Field(None, max_length=100)
    subtitle: str | None = Field(None, max_length=200)
    cover_url: str | None = Field(None, max_length=512)
    sort_order: int | None = None
    is_member_only: bool | None = None
    description: str | None = None
    learning_objectives: list[str] | None = Field(None, max_length=20)
    estimated_minutes: int | None = Field(None, ge=1, le=600)
    is_published: bool | None = None

    model_config = ConfigDict(extra="forbid")


class CourseRead(BaseModel):
    id: str
    code: str
    title: str
    subtitle: str | None = None
    cover_url: str | None = None
    stage: int
    sort_order: int
    is_member_only: bool
    description: str | None = None
    learning_objectives: list[str] = []
    estimated_minutes: int
    created_by_user_id: str | None = None
    is_published: bool
    published_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LessonCreate(BaseModel):
    course_id: str = Field(..., max_length=32)
    code: str = Field(..., min_length=1, max_length=40)
    title: str = Field(..., min_length=1, max_length=100)
    sort_order: int = Field(..., ge=0)
    duration_minutes: int = Field(15, ge=1, le=180)
    video_url: str | None = Field(None, max_length=512)
    transcript: str | None = None
    drill_ids: list[str] = Field(default_factory=list, max_length=20)
    pro_clip_ids: list[str] = Field(default_factory=list, max_length=20)
    quiz_payload: dict | None = None
    pass_criteria: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class LessonRead(BaseModel):
    id: str
    course_id: str
    code: str
    title: str
    sort_order: int
    duration_minutes: int
    video_url: str | None = None
    drill_ids: list[str] = []
    pro_clip_ids: list[str] = []
    quiz_payload: dict | None = None
    pass_criteria: dict = {}

    model_config = ConfigDict(from_attributes=True)


class UserCourseProgressUpdate(BaseModel):
    status: CourseStatusLiteral
    last_score: int | None = Field(None, ge=0, le=100)
    failed_reasons: list[str] | None = None
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")


class UserCourseProgressRead(BaseModel):
    id: str
    user_id: str
    lesson_id: str
    status: CourseStatusLiteral
    last_score: int | None = None
    attempts: int
    passed_at: datetime | None = None
    failed_reasons: list[str] = []
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CertificateRead(BaseModel):
    id: str
    user_id: str
    course_id: str
    stage: int
    cert_url: str | None = None
    issued_at: datetime
    revoked_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "CertificateRead",
    "CourseCreate",
    "CourseRead",
    "CourseStatusLiteral",
    "CourseUpdate",
    "LessonCreate",
    "LessonRead",
    "UserCourseProgressRead",
    "UserCourseProgressUpdate",
]
