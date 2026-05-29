"""P2-M11-04 · 阶段考核 Pydantic schema（W30 mock）.

对齐 docs/02 §6 课程接口（M11-04 子章节）。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.course import CertificateDetailRead


class LessonAttemptRequest(BaseModel):
    """POST /v1/lessons/{lesson_id}/attempt 请求体。"""

    swing_analysis_id: str = Field(
        ..., min_length=4, max_length=64,
        description="一期 swing_analyses.id；状态必须为 completed",
    )

    model_config = ConfigDict(extra="forbid")


class LessonAttemptResponse(BaseModel):
    """考核结果，含通关动画 / 重考所需全部字段。"""

    passed: bool
    score: int = Field(..., ge=0, le=100)
    min_score: int = Field(..., ge=0, le=100)
    attempts_used: int = Field(..., ge=0)
    max_attempts: int = Field(..., ge=1)
    failure_reason: Literal[
        "score_below_threshold",
        "engine_mode_mismatch",
    ] | None = None
    feedback: str = Field(..., max_length=200)
    # 升阶联动（kickoff §3.4）：本次通关是否触发本 course 升阶
    stage_upgraded: bool = False
    upgraded_to_stage: int | None = Field(default=None, ge=1, le=7)
    certificate: CertificateDetailRead | None = None


class PassCriteriaSchema(BaseModel):
    """lesson.pass_criteria JSONB 的 schema 校验（W31 后续 PR 用于 admin 编辑）。

    一期 service 仅以 raw dict 解析，本 schema 用于将来 admin 录入校验。
    """

    type: Literal["engine_score"] = "engine_score"
    engine_mode: Literal["full_swing", "putting", "chipping", "drive"] = "full_swing"
    phase: Literal[
        "overall",
        "setup",
        "takeaway",
        "top",
        "downswing",
        "impact",
        "follow_through",
    ] = "overall"
    min_score: int = Field(80, ge=0, le=100)
    max_attempts_per_day: int = Field(3, ge=1, le=20)

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "LessonAttemptRequest",
    "LessonAttemptResponse",
    "PassCriteriaSchema",
]
