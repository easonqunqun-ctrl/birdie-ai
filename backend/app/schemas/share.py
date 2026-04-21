"""分享相关 schema（W7-T5）."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ShareType = Literal["report", "invite_poster", "moments"]


class ShareLogRequest(BaseModel):
    """`POST /v1/shares/log` 请求体."""

    share_type: ShareType
    target_id: str | None = Field(
        default=None, description="`report` 场景 = analysis_id"
    )


class ShareLogResponse(BaseModel):
    id: str
    share_type: ShareType
    created_at: datetime


class PublicReportIssue(BaseModel):
    """公开报告中的问题项（脱敏版，不含关键帧 URL 与 description 细节）."""

    name: str
    severity: str


class PublicReport(BaseModel):
    """非本人访问时展示的脱敏报告（`GET /v1/analyses/{id}/public`）.

    只暴露足以激发"我也想拍一个"兴趣的最小集：
    - 综合评分 + 等级
    - 分享者昵称（脱敏）+ 拍摄日期
    - 球杆/角度元信息
    - 缩略图（公共可访问 CDN URL）
    - 关键问题**仅名称 + 严重度**，最多 3 条且只含 high/medium
    - 不含：原视频、骨骼视频、recommendations、phase_scores/phase_timestamps、user_id
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    overall_score: int | None = None
    score_level: str | None = None

    camera_angle: str
    club_type: str
    thumbnail_url: str | None = None

    issues: list[PublicReportIssue] = Field(default_factory=list)
    issues_total: int = 0

    analyzed_at: datetime | None = None
    owner_nickname_masked: str
