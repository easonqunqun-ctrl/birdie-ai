"""M8-07 · 教练教学报告 schema."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class CoachRecapCreateRequest(BaseModel):
    session_date: date
    student_ids: list[str] = Field(min_length=1, max_length=20)
    analysis_ids: list[str] = Field(min_length=1, max_length=50)
    coach_manual_notes: str | None = Field(default=None, max_length=2000)


class CoachRecapCreateResponse(BaseModel):
    recap_id: str
    ai_summary: str
    status: str
    ai_summary_model: str | None = None


class CoachRecapExportPdfResponse(BaseModel):
    pdf_url: str
    pdf_url_expires_at: datetime


class CoachRecapListItem(BaseModel):
    id: str
    session_date: date
    student_ids: list[str]
    analysis_ids: list[str]
    status: str
    ai_summary: str | None = None
    pdf_url: str | None = None
    pdf_url_expires_at: datetime | None = None
    created_at: datetime


class CoachRecapListResponse(BaseModel):
    items: list[CoachRecapListItem]
    total: int
