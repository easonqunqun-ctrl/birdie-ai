"""挥杆分析相关 Pydantic schema（对齐 docs/02-API接口设计文档.md §三 /analyses）."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ==================== 通用枚举（字符串 Literal 保留给 Pydantic 做校验） ====================
CameraAngle = Literal["face_on", "down_the_line"]
ClubType = Literal[
    "driver",
    "fairway_wood",
    "iron_3",
    "iron_4",
    "iron_5",
    "iron_6",
    "iron_7",
    "iron_8",
    "iron_9",
    "wedge",
    "putter",
    "unknown",
]
VideoFileType = Literal["video/mp4", "video/quicktime"]
AnalysisStatus = Literal["pending", "processing", "completed", "failed"]
AnalysisStage = Literal[
    "preprocessing",
    "pose_estimating",
    "phase_segmenting",
    "scoring",
    "diagnosing",
    "generating",
]
IssueSeverity = Literal["high", "medium", "low"]


# ==================== 3.1 POST /v1/analyses/upload-token ====================
class UploadTokenRequest(BaseModel):
    """申请上传凭证。前端在调用 wx.chooseMedia 之后，把视频元信息传过来做配额/规格预检."""

    file_name: str = Field(..., max_length=255, description="原始文件名")
    file_size: int = Field(..., gt=0, description="文件大小（字节）")
    file_type: VideoFileType = Field(..., description="MIME 类型")
    duration: float = Field(..., gt=0, description="视频时长（秒）")


class MinioPostFields(BaseModel):
    """MinIO 预签名 POST policy 返回的表单字段集合（原样透传给客户端做 form-data 上传）."""

    model_config = ConfigDict(extra="allow")

    policy: str
    key: str
    x_amz_algorithm: str = Field(..., alias="x-amz-algorithm")
    x_amz_credential: str = Field(..., alias="x-amz-credential")
    x_amz_date: str = Field(..., alias="x-amz-date")
    x_amz_signature: str = Field(..., alias="x-amz-signature")


class UploadTokenResponse(BaseModel):
    """发给客户端的直传凭证。客户端按 `upload_url` + `fields` 做 multipart/form-data POST."""

    upload_id: str = Field(..., description="后续 POST /analyses 引用该 id")
    upload_url: str = Field(..., description="直传的完整 URL（公网可达）")
    bucket: str
    key: str = Field(..., description="对象存储路径（预分配）")
    fields: dict[str, str] = Field(..., description="form-data 需要附带的字段（policy / x-amz-* 等）")
    expires_at: datetime = Field(..., description="凭证过期时间（UTC）")
    max_file_size: int = Field(..., description="最大文件大小（字节）")


# ==================== 3.2 POST /v1/analyses ====================
class CreateAnalysisRequest(BaseModel):
    upload_id: str = Field(..., description="POST /upload-token 返回的 upload_id")
    camera_angle: CameraAngle
    club_type: ClubType


class CreateAnalysisResponse(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    queue_position: int = Field(..., description="队列位置（0 表示下一个处理）")
    estimated_seconds: int = Field(..., description="预计等待秒数")
    created_at: datetime


# ==================== 3.3 GET /v1/analyses/{id}/status ====================
class AnalysisStatusError(BaseModel):
    code: int
    message: str
    quota_refunded: bool


class AnalysisStatusResponse(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    stage: AnalysisStage | None = None
    stage_progress: int = Field(default=0, ge=0, le=100)
    estimated_remaining_seconds: int = Field(default=0, ge=0)
    error: AnalysisStatusError | None = None


# ==================== 3.4 GET /v1/analyses/{id} ====================
class PhaseScore(BaseModel):
    score: int = Field(..., ge=0, le=100)
    label: str
    is_weakest: bool = False


class PhaseWindow(BaseModel):
    """挥杆阶段时间窗口（秒）."""

    start: float = Field(..., ge=0)
    end: float = Field(..., ge=0)


class IssueItem(BaseModel):
    type: str
    name: str
    severity: IssueSeverity
    description: str
    key_frame_url: str | None = None
    key_frame_timestamp: float | None = None


class RecommendationItem(BaseModel):
    """训练建议。`drill_id` 指向 drills 动作库；`name/steps` 等在 T5 报告页展示时由前端或后端 join 出来，
    T1 阶段为简化只返回骨架，T2 写结果落库时一起把冗余字段带出来."""

    drill_id: str
    target_issue: str | None = None
    sort_order: int = 0


class AnalysisReportResponse(BaseModel):
    """完整分析报告。MVP §4.3 报告页所需字段全在这里."""

    id: str
    user_id: str
    status: AnalysisStatus
    camera_angle: CameraAngle
    club_type: ClubType

    video_url: str
    video_duration: float | None = None
    skeleton_video_url: str | None = None
    skeleton_data_url: str | None = None
    thumbnail_url: str | None = None

    overall_score: int | None = None
    score_change: int | None = None
    score_level: str | None = Field(
        default=None,
        description="excellent / great / good / fair / needs_improvement（由 overall_score 派生）",
    )
    phase_scores: dict[str, PhaseScore] | None = None
    phase_timestamps: dict[str, PhaseWindow] | None = None

    issues: list[IssueItem] = Field(default_factory=list)
    recommendations: list[RecommendationItem] = Field(default_factory=list)

    share_card_url: str | None = None
    analyzed_at: datetime | None = None
    created_at: datetime


# ==================== 3.5 GET /v1/analyses (list) ====================
class AnalysisListItem(BaseModel):
    id: str
    camera_angle: CameraAngle
    club_type: ClubType
    overall_score: int | None = None
    score_change: int | None = None
    thumbnail_url: str | None = None
    status: AnalysisStatus
    analyzed_at: datetime | None = None
    created_at: datetime


class AnalysisListQuery(BaseModel):
    """列表筛选参数（通过 FastAPI Query 直接注入，单独建 schema 方便单元测试）."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)
    club_type: ClubType | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


# ==================== 内部常量 ====================

# 分阶段预计剩余秒数（基线 25s，T2 接入 Celery 后以实际阶段为准）
STAGE_ETA_SECONDS: dict[str, int] = {
    "pending": 25,
    "preprocessing": 20,
    "pose_estimating": 15,
    "phase_segmenting": 12,
    "scoring": 8,
    "diagnosing": 5,
    "generating": 2,
    "completed": 0,
    "failed": 0,
}


def score_level(overall: int | None) -> str | None:
    """按 MVP §4.3 的评分等级表映射。None 表示尚未完成或失败."""
    if overall is None:
        return None
    if overall >= 90:
        return "excellent"
    if overall >= 80:
        return "great"
    if overall >= 70:
        return "good"
    if overall >= 60:
        return "fair"
    return "needs_improvement"


__all__ = [
    "STAGE_ETA_SECONDS",
    "AnalysisListItem",
    "AnalysisListQuery",
    "AnalysisReportResponse",
    "AnalysisStage",
    "AnalysisStatus",
    "AnalysisStatusError",
    "AnalysisStatusResponse",
    "CameraAngle",
    "ClubType",
    "CreateAnalysisRequest",
    "CreateAnalysisResponse",
    "IssueItem",
    "IssueSeverity",
    "MinioPostFields",
    "PhaseScore",
    "PhaseWindow",
    "RecommendationItem",
    "UploadTokenRequest",
    "UploadTokenResponse",
    "VideoFileType",
    "score_level",
]
