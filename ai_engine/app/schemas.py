"""AI Engine 输入输出 schema."""

from typing import Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """挥杆分析请求."""

    analysis_id: str = Field(..., description="后端分配的分析 ID，用于回调")
    video_url: str = Field(..., description="视频文件 URL（COS/MinIO）")
    camera_angle: Literal["face_on", "down_the_line"]
    club_type: str = Field(..., description="球杆类型")
    # P2-M7-11/12：分析模式。full_swing=全挥杆（默认）；putting/chipping 独立 pipeline。
    mode: Literal["full_swing", "putting", "chipping"] = Field(
        default="full_swing",
        description="分析模式：full_swing / putting / chipping；与 club_type 不匹配回 50123",
    )
    callback_url: str | None = Field(default=None, description="完成后回调后端的 URL")
    # M7-14：后端传 user_id 用于灰度分桶；未传时所有请求走 V1
    user_id_hint: str | None = Field(
        default=None,
        description="用户 ID hint，仅用于 V2 灰度分桶（不落库 ai_engine 侧）",
    )
    # M7-14：覆盖灰度判定（仅供运维 / 单测 / shadow 回放使用）
    force_engine_version: Literal["v1", "v2"] | None = Field(
        default=None,
        description="强制指定 engine_version，跳过灰度分桶；仅运维/单测使用",
    )
    # P2-M7-13：多挥视频中用户指定的候选段索引（0-based）；None → 自动选第一段非试挥
    selected_swing_index: int | None = Field(
        default=None,
        ge=0,
        description="多挥视频要分析的段索引；省略则引擎自动选第一段非试挥",
    )


class SwingCandidateItem(BaseModel):
    """P2-M7-13 · 单段挥杆候选（供客户端 select-swing UI 消费）。"""

    start_frame: int
    end_frame: int
    is_practice: bool
    confidence: float = Field(ge=0.0, le=1.0)
    start_time_sec: float
    end_time_sec: float
    preview_frame_url: str | None = Field(
        default=None,
        description="该段 impact 附近抽帧 JPG（MinIO URL；detect-swings 可选返回）",
    )


class PhaseScore(BaseModel):
    score: int
    label: str
    is_weakest: bool = False


class IssueItem(BaseModel):
    type: str
    name: str
    severity: Literal["high", "medium", "low"]
    description: str
    key_frame_timestamp: float | None = None
    # W6-T3：每条 issue 的关键帧截图（MinIO URL）。后端 schema 已存在同名字段，
    # 这里补齐避免 ai_engine→backend 映射时丢字段。MVP 期 ai_engine 在 visualize 步骤生成。
    key_frame_url: str | None = None
    # P2-M7-06：每诊断置信度（0-1）+ 档位（confirmed/leaning/hidden）
    # V1 路径不填；V2 路径必填。客户端按 tier 决定红/蓝/折叠区。
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="P2-M7-06 每诊断 confidence"
    )
    confidence_tier: Literal["confirmed", "leaning", "hidden"] | None = Field(
        default=None, description="P2-M7-06 档位"
    )


class RecommendationItem(BaseModel):
    drill_id: str
    name: str
    target_issue: str
    description: str
    duration_minutes: int
    sets: int
    steps: list[str]


class PhaseTimestamps(BaseModel):
    setup: dict[str, float]
    backswing: dict[str, float]
    top: dict[str, float]
    downswing: dict[str, float]
    impact: dict[str, float]
    follow_through: dict[str, float]


class AnalyzeResult(BaseModel):
    """完整分析结果."""

    analysis_id: str
    status: Literal["completed", "failed"]
    # M7-14：每份报告显式带版本号；V1 默认 "v1"，V2 路径写 "v2"（FR-1）
    engine_version: Literal["v1", "v2"] = "v1"
    # P2-M7-11/12：分析模式回显。putting/chipping 的 phase_scores 键与 full_swing 不同构。
    analysis_mode: Literal["full_swing", "putting", "chipping"] = "full_swing"
    overall_score: int | None = None
    phase_scores: dict[str, PhaseScore] | None = None
    phase_timestamps: PhaseTimestamps | None = None
    issues: list[IssueItem] = Field(default_factory=list)
    recommendations: list[RecommendationItem] = Field(default_factory=list)

    skeleton_video_url: str | None = None
    skeleton_data_url: str | None = None
    thumbnail_url: str | None = None
    # 骨骼异步：主分析先 completed；backend Celery 再调 /derive-skeleton
    skeleton_pending: bool = False
    normalized_video_url: str | None = Field(
        default=None,
        description="defer 骨骼时暂存的归一化视频 URL（仅供 /derive-skeleton，不暴露给 C 端）",
    )

    duration_ms: int | None = None
    error_code: int | None = None
    error_message: str | None = None
    quality_warnings: list[str] = Field(
        default_factory=list,
        description="非阻断质量提示 machine codes，如 low_light / camera_shake",
    )
    engine_warnings: list[dict] = Field(
        default_factory=list,
        description=(
            "P2-M7-02：引擎侧解码/归一化诊断；每项 {code,level,detail,ts}。"
            "V1 路径始终为空数组；V2 路径填值。≤32 项，超出截断。"
        ),
    )
    # P2-M7-06：三层置信度（详 docs/release-notes/p2-m7-06-confidence-pipeline-kickoff.md）
    analysis_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "P2-M7-06 整体置信度（0-1）。V1 引擎遗留报告兜底 1.0；"
            "客户端 <0.5 时展示「建议重拍」CTA，0.5-0.75 中可信色块，≥0.75 高可信。"
        ),
    )
    feature_confidences: dict[str, float] = Field(
        default_factory=dict,
        description="P2-M7-06 每特征 confidence（feature_name → 0-1）",
    )
    # P2-M7-13：多挥候选列表 + 实际分析段索引（单段视频为空列表 / index=0）
    swing_candidates: list[SwingCandidateItem] = Field(
        default_factory=list,
        description="检测到的挥杆候选段；客户端 select-swing UI 用",
    )
    selected_swing_index: int | None = Field(
        default=None,
        description="本次分析使用的候选段索引（0-based）",
    )
    # M10-01/02：推杆/切杆 mode 专属特征分（pendulum_stability 等）
    mode_feature_scores: dict[str, int] | None = Field(
        default=None,
        description="mode=putting/chipping 时各专属特征 0-100 分",
    )
    phase_highlights: list[str] = Field(
        default_factory=list,
        description="阶段亮点肯定话术（V2；docs/20 §4.3）",
    )


class DeriveSkeletonRequest(BaseModel):
    """异步补渲染骨骼视频（分析主路径已 completed）。"""

    analysis_id: str
    normalized_video_url: str | None = Field(
        default=None, description="主分析上传的归一化视频；缺省按约定 key 取"
    )
    skeleton_data_url: str | None = Field(
        default=None, description="pose parquet URL；缺省按约定 key 取"
    )
    video_url: str | None = Field(
        default=None, description="归一化视频缺失时的原片回退"
    )


class DeriveSkeletonResult(BaseModel):
    analysis_id: str
    status: Literal["completed", "failed"]
    skeleton_video_url: str | None = None
    error_message: str | None = None
    elapsed_ms: int = 0


class PrecheckRequest(BaseModel):
    analysis_id: str = Field(..., description="后端分配的分析 ID")
    video_url: str = Field(..., description="视频文件 URL（COS/MinIO）")


class PrecheckResult(BaseModel):
    analysis_id: str
    status: Literal["passed", "blocked"]
    quality_warnings: list[str] = Field(default_factory=list)
    error_code: int | None = None
    error_message: str | None = None
    elapsed_ms: int = 0
    scan_elapsed_ms: int = 0


class DetectSwingsRequest(BaseModel):
    """P2-M7-13 · 上传后多挥候选探测（不跑评分）。"""

    analysis_id: str = Field(..., description="探测任务 ID（可用 upload_id）")
    video_url: str = Field(..., description="已上传视频 URL")
    mode: Literal["full_swing"] = Field(
        default="full_swing",
        description="当前仅 full_swing 支持多挥探测",
    )


class DetectSwingsResult(BaseModel):
    analysis_id: str
    status: Literal["ok", "failed"]
    swing_candidates: list[SwingCandidateItem] = Field(default_factory=list)
    default_selected_index: int = Field(
        default=0,
        ge=0,
        description="建议默认段（第一段非试挥）",
    )
    # P2-M7-R1 / M7-04-UI：上传后机位预选（低置信时为 null，客户端保持用户默认）
    suggested_camera_angle: Literal["face_on", "down_the_line"] | None = Field(
        default=None,
        description="建议默认机位；confidence≥0.7 且 detected 非 oblique 时返回",
    )
    detected_camera_angle: Literal["face_on", "down_the_line", "oblique"] | None = Field(
        default=None,
        description="启发式检测机位（含 oblique 中间态）",
    )
    camera_angle_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="机位检测置信度 0-1",
    )
    error_code: int | None = None
    error_message: str | None = None
