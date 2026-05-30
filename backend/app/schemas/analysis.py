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
AnalysisMode = Literal["full_swing", "putting", "chipping"]


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
    mode: AnalysisMode = Field(
        default="full_swing",
        description="分析模式：full_swing（默认）/ putting / chipping",
    )
    target_yardage: int | None = Field(
        default=None,
        ge=1,
        le=400,
        description="本次击球目标码数（码）；仅 full_swing 且 `PHASE2_YARDAGE_BOOK_ENABLED` 时有效，供 yardage book 反推",
    )
    selected_swing_index: int | None = Field(
        default=None,
        ge=0,
        description="多挥视频要分析的段索引（0-based）；仅 full_swing；省略则 ai_engine 自动选第一段非试挥",
    )


class CreateAnalysisResponse(BaseModel):
    analysis_id: str
    status: AnalysisStatus
    queue_position: int = Field(..., description="队列位置（0 表示下一个处理）")
    estimated_seconds: int = Field(..., description="预计等待秒数")
    created_at: datetime


class SwingCandidateItem(BaseModel):
    """P2-M7-13 · 单段挥杆候选（与 ai_engine SwingCandidateItem 对齐）."""

    start_frame: int
    end_frame: int
    is_practice: bool
    confidence: float = Field(ge=0.0, le=1.0)
    start_time_sec: float
    end_time_sec: float
    preview_frame_url: str | None = None


class DetectSwingsResponse(BaseModel):
    """POST /v1/analyses/uploads/{upload_id}/detect-swings 成功响应."""

    upload_id: str
    swing_candidates: list[SwingCandidateItem] = Field(default_factory=list)
    default_selected_index: int = Field(
        default=0,
        ge=0,
        description="建议默认段（第一段非试挥）",
    )


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
    # P2-M7-06：每诊断置信度 + 档位（V1 路径为 None）
    # confidence_tier: confirmed/leaning/hidden
    #   - confirmed: 客户端正常展示
    #   - leaning:   "可能存在……"语气
    #   - hidden:    默认折叠到「AI 不太确定」区，避免低质量诊断打扰用户（W10-B3）
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_tier: Literal["confirmed", "leaning", "hidden"] | None = None


class EngineWarningItem(BaseModel):
    """P2-W10：W8 落地的引擎诊断条目，从 ai_engine.AnalyzeResult 原样透传.

    code 取值参考 ai_engine/app/pipeline/engine_warnings.py KNOWN_CODES，含：
    - 解码：decoded_h264 / decoded_hevc / decoded_vp9
    - HDR：hdr_tonemapped
    - 帧率：slowmo_detected / nominal_fps_used / fps_upsampled / fps_downsampled
    - 音频：audio_kept / audio_dropped
    - 灰度：fallback_to_v1
    level: info（默认）/ warn / error；W10 客户端仅在调试浮层展示，不在主报告区显眼提示
    """

    code: str
    level: Literal["info", "warn", "error"] = "info"
    detail: str | None = None
    ts: float | None = Field(default=None, description="Unix epoch 秒，由 ai_engine 生成")


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
    analysis_mode: AnalysisMode = "full_swing"
    # M10-01：推杆 mode 专属 4 维度分；仅 analysis_mode=putting 时有值
    putting_features: dict[str, PhaseScore] | None = None
    # M10-02：切杆 mode 专属 3 维度分；仅 analysis_mode=chipping 时有值
    chipping_features: dict[str, PhaseScore] | None = None
    # M7-14：报告永久按落库 engine_version 渲染。客户端按值开关 V2 新字段（如 confidence）。
    engine_version: Literal["v1", "v2"] = "v1"

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
    # P2-M7-06：整体置信度（V1 报告兜底 1.0；客户端 <0.5 展示「建议重拍」CTA）
    analysis_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="P2-M7-06 整体置信度 0-1；V1 引擎兜底 1.0",
    )
    feature_confidences: dict[str, float] = Field(
        default_factory=dict,
        description="P2-M7-06 每特征 confidence",
    )
    # P2-W10：W8 引擎诊断（codec/HDR/慢动作/fps/audio/fallback），客户端调试浮层展示
    engine_warnings: list[EngineWarningItem] = Field(
        default_factory=list,
        description="P2-W10 引擎诊断结构化条目；V1 引擎或老报告返回空数组",
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
    # P2-W11：列表卡片可信度小标签 + V2 角标用
    # V1 / 老报告 engine_version 缺省按 "v1" 兜底；analysis_confidence 缺省 null（前端不渲染小标签）
    engine_version: Literal["v1", "v2"] = "v1"
    analysis_confidence: float | None = None


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
    phase_scores: dict[str, int] | None = Field(
        default=None,
        description="六维阶段分扁平 map，如 setup→80；无六维数据时为 null",
    )
    # P2-W12-1：让进步曲线点能按 trust tier（高/中/低）着色——用户在曲线上
    # 一眼看出"哪几次是 AI 高可信、哪几次曲线点其实是低置信不能完全信"。
    # 老 V1 报告兜底 engine_version="v1" / analysis_confidence=None
    # （客户端按 engine_version=="v2" 路由决定是否换色）。
    engine_version: Literal["v1", "v2"] = "v1"
    analysis_confidence: float | None = None


class AnalysisProgressResponse(BaseModel):
    points: list[AnalysisProgressPoint]


class ScorePercentileResponse(BaseModel):
    """P2-W16-A · ENG-05 · 同水平+同器材的得分分位（"你击败了 X% 同水平用户"）.

    设计要点
    --------
    - **cohort 维度**：``golf_level`` （User 表，beginner/amateur/intermediate/advanced
      等）+ ``club_type``。用户未填 ``golf_level`` 时不限定 level，回落到"全部 club_type
      cohort"。
    - **样本量阈值**：``cohort_size < MIN_COHORT_SIZE`` 时 ``percentile = null``，
      客户端隐藏分位 UI（避免拿 1-2 个对比就出"击败 50%"这种误导）。
    - **基准**：每个对照用户取其**最近一条**同 club_type 完成态分析的 ``overall_score``
      （不是平均，避免老用户被早期低分拉低）。
    - **性能**：DB 端 1 次查询出 cohort 分数列表，Python 算 percentile / median；
      cohort 上限 1000 行（`MAX_COHORT_ROWS`），防止热门 club_type 单查询爆。
    - **隐私**：响应只暴露聚合（cohort_size / median / percentile），不暴露
      他人 user_id / 具体分数。
    """

    user_score: int | None = Field(
        ..., description="当前用户最近一次该 club_type 的综合分；无任何分析时 null"
    )
    percentile: int | None = Field(
        ...,
        ge=0,
        le=100,
        description="击败 N% 同水平+同器材用户（向下取整 0-100）；样本不足时 null",
    )
    cohort_size: int = Field(
        ..., ge=0, description="参与对比的同水平+同器材用户数（不含当前用户）"
    )
    cohort_label: str = Field(
        ...,
        description="人话化 cohort 描述，如「中级 / 七号铁」；客户端可直接展示",
    )
    median: int | None = Field(
        None, description="cohort 中位数（P50）；样本不足时 null"
    )
    club_type: str
    golf_level: str | None = Field(None, description="当前用户的水平；未填时为 null")
    computed_at: datetime


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
    "ScorePercentileResponse",
    "ShareCardResponse",
    "UploadTokenRequest",
    "UploadTokenResponse",
    "VideoFileType",
    "estimate_swing_remaining_seconds",
    "score_level",
]
