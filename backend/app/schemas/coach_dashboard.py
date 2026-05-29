"""M8-06 · 教练学员看板 schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CoachDashboardStudentItem(BaseModel):
    student_user_id: str
    display_name: str
    avatar_url: str | None = None
    relation_id: str
    analyses_7d: int = 0
    last_analysis_at: datetime | None = None
    last_annotation_at: datetime | None = None
    pending_tasks: int = 0
    needs_response: bool = False


class CoachDashboardListResponse(BaseModel):
    students: list[CoachDashboardStudentItem] = Field(default_factory=list)
    total: int
    cached_at: datetime | None = None


class CoachDashboardAnalysisBrief(BaseModel):
    id: str
    created_at: datetime
    overall_score: int | None = None
    club_type: str | None = None
    status: str


class CoachDashboardAnnotationBrief(BaseModel):
    id: str
    annotation_type: str
    text_content: str | None = None
    created_at: datetime


class CoachDashboardTaskBrief(BaseModel):
    id: str
    drill_name: str | None = None
    target_count: int
    status: str
    created_at: datetime


class CoachDashboardDetailResponse(BaseModel):
    student_user_id: str
    display_name: str
    avatar_url: str | None = None
    relation_id: str
    analyses_7d: int = 0
    last_analysis_at: datetime | None = None
    last_annotation_at: datetime | None = None
    pending_tasks: int = 0
    needs_response: bool = False
    recent_analyses: list[CoachDashboardAnalysisBrief] = Field(default_factory=list)
    recent_annotations: list[CoachDashboardAnnotationBrief] = Field(default_factory=list)
    pending_coach_tasks: list[CoachDashboardTaskBrief] = Field(default_factory=list)
    cached_at: datetime | None = None
