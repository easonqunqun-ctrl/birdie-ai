"""M8-05 · 教练作业派发 schema."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CoachAssignedSourceType = Literal["drill", "custom_video"]
CoachAssignedStatus = Literal["assigned", "started", "done", "expired"]


class CoachTaskAssignRequest(BaseModel):
    student_user_id: str = Field(min_length=1, max_length=32)
    source_type: CoachAssignedSourceType = "drill"
    drill_id: str | None = Field(default=None, max_length=32)
    target_week: date
    target_count: int = Field(default=1, ge=1, le=99)
    target_issue: str | None = Field(default=None, max_length=64)
    coach_note: str | None = Field(default=None, max_length=500)


class CoachTaskStudentBrief(BaseModel):
    id: str
    nickname: str | None = None


class CoachTaskDrillBrief(BaseModel):
    id: str
    name: str


class CoachAssignedTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    coach_user_id: str
    student_user_id: str
    relation_id: str
    source_type: CoachAssignedSourceType
    drill_id: str | None
    target_week: date
    target_count: int
    target_issue: str | None
    coach_note: str | None
    training_task_id: str | None
    status: CoachAssignedStatus
    completed_at: datetime | None
    created_at: datetime
    student: CoachTaskStudentBrief | None = None
    drill: CoachTaskDrillBrief | None = None


class CoachAssignedTaskListResponse(BaseModel):
    items: list[CoachAssignedTaskRead]
    total: int
