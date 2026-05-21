"""挥杆分析相关 Pydantic schema（对齐 docs/02-API接口设计文档.md §三 /analyses）."""

import math
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

    quality_warnings: list[str] = Field(
        default_factory=list,
        description="非阻断质量提示（与 ai_engine 相同 machine code）；空列表表示无",
    )

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


class AnalysisListPaywall(BaseModel):
    """免费用户的历史报告条数被截断时返回，提示前端展示升级 CTA（docs/01 §8.2）.

    - ``capped_to``：免费用户能看到的最近 N 份（当前 N=3）
    - ``total_count``：用户实际拥有的真实总数（含被截断的）
    - ``reason``：``free_user_history_limit``，保留以便未来扩展（如配额型截断）
    """

    reason: str = "free_user_history_limit"
    capped_to: int
    total_count: int


class AnalysisListPage(BaseModel):
    """``GET /v1/analyses`` 的响应载荷：在通用 PageData 基础上叠加 ``paywall`` 元信息."""

    items: list[AnalysisListItem]
    total: int
    page: int
    page_size: int
    has_more: bool
    paywall: AnalysisListPaywall | None = None


# ==================== 内部常量 ====================

# 与 `tasks/analysis_tasks.py` 中装饰性阶段推进共用同一张时间表（从这里 import）。
# 单位：秒。总和应与 AI 管线「装饰进度」口径一致（真实引擎可能比表更慢 ⇒ 下文 ETA 单独加 slack）。
SWING_STAGE_TIMELINE: list[tuple[str, int]] = [
    ("preprocessing", 4),
    ("pose_estimating", 8),
    ("phase_segmenting", 3),
    ("scoring", 3),
    ("diagnosing", 3),
    ("generating", 2),
]

# STAGE_ETA_SECONDS 与 SWING_STAGE_TIMELINE 分工（请勿把逐项数字逐项对齐 timeline）：
# - SWING_STAGE_TIMELINE：status=processing 时装饰进度、`estimate_swing_remaining_seconds` 的主时间轴。
# - STAGE_ETA_SECONDS：仅用于 pending（未被 worker pickup 的体感）及 unknown stage / 兜底查表，
#   以及 completed/failed 等固定 0 字段；不要求与各 processing 阶段的秒数一致。
STAGE_ETA_SECONDS: dict[str, int] = {
    "pending": 18,
    "preprocessing": 20,
    "pose_estimating": 15,
    "phase_segmenting": 12,
    "scoring": 8,
    "diagnosing": 5,
    "generating": 2,
    "completed": 0,
    "failed": 0,
}


def estimate_swing_remaining_seconds(
    *,
    status: str,
    stage: str | None,
    stage_progress: int,
) -> int:
    """`/status.estimated_remaining_seconds`：基于当前 phase + stage_progress 估算剩余等待秒数."""

    if status == "completed" or status == "failed":
        return 0
    if status == "pending":
        return STAGE_ETA_SECONDS["pending"]

    prog = max(0, min(99, stage_progress))
    # stage_progress→99：本 phase 快走完了；`(99-prog)` 避免出现 0 → 与用户体感「卡住」相悖
    in_phase_frac = max(1, 99 - prog) / 99

    idx = next(
        (i for i, (name, _) in enumerate(SWING_STAGE_TIMELINE) if name == stage),
        None,
    )
    if idx is None:
        # 后端新增 stage 或未匹配：降级为静态表（至少不为 0）
        return max(12, STAGE_ETA_SECONDS.get(stage or "", 25))

    remaining = SWING_STAGE_TIMELINE[idx][1] * in_phase_frac
    for j in range(idx + 1, len(SWING_STAGE_TIMELINE)):
        remaining += SWING_STAGE_TIMELINE[j][1]

    # 装饰时间表总和低于 AI_ENGINE_TIMEOUT；略收紧 slack，减少「还剩很久」的误判
    slack = 12
    return max(
        8,
        min(78, math.ceil(remaining + slack)),
    )


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


class ShareCardResponse(BaseModel):
    """分享用小程序码 PNG 的公网 URL（对象存储直链）."""

    wxa_code_url: str = Field(..., description="小程序码图片 URL，可用作分享 imageUrl 等")


class AnalysisProgressPoint(BaseModel):
    """MVP §6 进步曲线：按时间序的得分点（仅正式分析，不含 sample）."""

    analysis_id: str
    analyzed_at: datetime
    overall_score: int


class AnalysisProgressResponse(BaseModel):
    points: list[AnalysisProgressPoint]


__all__ = [
    "STAGE_ETA_SECONDS",
    "SWING_STAGE_TIMELINE",
    "AnalysisListItem",
    "AnalysisListPage",
    "AnalysisListPaywall",
    "AnalysisListQuery",
    "AnalysisProgressPoint",
    "AnalysisProgressResponse",
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
    "ShareCardResponse",
    "UploadTokenRequest",
    "UploadTokenResponse",
    "VideoFileType",
    "estimate_swing_remaining_seconds",
    "score_level",
]
