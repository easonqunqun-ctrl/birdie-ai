"""M8-04 / M12-09 · 教练报告批注 schema."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pro_library import ProPlayerRead, ProSwingClipRead

CoachAnnotationTypeLiteral = Literal["voice", "text", "sketch", "video_ref"]


class CoachAnnotationCreate(BaseModel):
    annotation_type: CoachAnnotationTypeLiteral
    pro_clip_id: str | None = Field(default=None, max_length=32)
    text_content: str | None = Field(default=None, max_length=500)


class CoachAnnotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_id: str
    annotation_type: CoachAnnotationTypeLiteral
    pro_clip_id: str | None
    text_content: str | None
    audit_status: str | None = None
    is_visible: bool
    created_at: datetime


class CoachAnnotationClipRefRead(CoachAnnotationRead):
    """学员侧展示：展开职业镜头 + 球手（clip 下架时为 null）."""

    clip: ProSwingClipRead | None = None
    player: ProPlayerRead | None = None
    clip_unavailable: bool = False
