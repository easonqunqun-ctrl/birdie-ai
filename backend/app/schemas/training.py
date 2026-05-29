"""训练计划 / 打卡相关 Pydantic schema（W7-T3）."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TaskStatus = Literal["pending", "completed"]
TaskKind = Literal["standard", "pro_clip_try_it"]
Difficulty = Literal["easy", "medium", "hard"]


class DrillDetail(BaseModel):
    """动作库条目（前端也可以内置一份，拉这个做兜底/升级）."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    target_issues: list[str] = Field(default_factory=list)
    description: str
    steps: list[str] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)
    duration_minutes: int
    sets: int | None = None
    difficulty: Difficulty
    illustration_url: str | None = None
    video_url: str | None = None


class TrainingTaskItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan_id: str
    drill_id: str
    scheduled_date: date
    sort_order: int
    status: TaskStatus
    completed_at: datetime | None = None
    verification_analysis_id: str | None = None
    task_kind: TaskKind = "standard"
    pro_clip_id: str | None = None
    pro_player_name: str | None = None
    pro_clip_unavailable: bool = False


class TrainingPlanDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    week_start: date
    week_end: date
    source_analysis_id: str | None = None
    ai_summary: str | None = None
    total_tasks: int
    completed_tasks: int
    tasks: list[TrainingTaskItem] = Field(default_factory=list)
    created_at: datetime


class CompleteTaskRequest(BaseModel):
    """打卡请求（notes/duration 可选）."""

    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    notes: str | None = Field(default=None, max_length=500)


class CompleteTaskResponse(BaseModel):
    task: TrainingTaskItem
    current_streak_days: int
    plan_completed_tasks: int
    plan_total_tasks: int


class PracticeLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    drill_id: str
    task_id: str | None = None
    practice_date: date
    duration_minutes: int | None = None
    notes: str | None = None
    created_at: datetime
