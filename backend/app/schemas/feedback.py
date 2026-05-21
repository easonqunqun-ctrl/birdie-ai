"""意见反馈 Pydantic schema（对齐 docs/02 §2.6）."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """POST /v1/feedback 请求体."""

    content: str = Field(..., min_length=1, max_length=500, description="反馈正文")
    contact: str | None = Field(
        None, max_length=128, description="联系方式（手机号/邮箱/微信号，选填）"
    )


class FeedbackCreated(BaseModel):
    """POST /v1/feedback 响应数据."""

    feedback_id: str
