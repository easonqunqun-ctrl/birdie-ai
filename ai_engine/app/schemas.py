"""AI Engine 输入输出 schema."""

from typing import Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """挥杆分析请求."""

    analysis_id: str = Field(..., description="后端分配的分析 ID，用于回调")
    video_url: str = Field(..., description="视频文件 URL（COS/MinIO）")
    camera_angle: Literal["face_on", "down_the_line"]
    club_type: str = Field(..., description="球杆类型")
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
    overall_score: int | None = None
    phase_scores: dict[str, PhaseScore] | None = None
    phase_timestamps: PhaseTimestamps | None = None
    issues: list[IssueItem] = Field(default_factory=list)
    recommendations: list[RecommendationItem] = Field(default_factory=list)

    skeleton_video_url: str | None = None
    skeleton_data_url: str | None = None
    thumbnail_url: str | None = None

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
