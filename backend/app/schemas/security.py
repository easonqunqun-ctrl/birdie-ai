"""内容安全相关 schema（W8-T5）."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MediaCheckResponse(BaseModel):
    """`POST /v1/security/media-check` 响应。

    - `passed=True`：通过（或 fail open 兜底）；可继续后续业务
    - `passed=False`：内容违规，前端必须阻断后续上传
    - `reason`：仅失败或 fail open 时填；passed=True 且无异常时为 None
    """

    passed: bool = Field(description="是否通过审核")
    reason: str | None = Field(default=None, description="失败原因或 fail open 说明")
