"""挥杆分析相关模型（对齐 docs/03-数据库设计文档.md 3.2-3.4 节）."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AnalysisQuota(Base, TimestampMixin):
    """月度分析配额."""

    __tablename__ = "analysis_quotas"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    quota_month: Mapped[str] = mapped_column(String(7), nullable=False)  # 2026-04
    used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total: Mapped[int] = mapped_column(Integer, default=3, server_default="3")  # -1 = 无限
    bonus: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("user_id", "quota_month", name="uq_analysis_quota"),
        Index("idx_analysis_quotas_lookup", "user_id", "quota_month"),
    )


class SwingAnalysis(Base, TimestampMixin):
    """挥杆分析记录."""

    __tablename__ = "swing_analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 输入
    video_url: Mapped[str] = mapped_column(String(512), nullable=False)
    video_duration: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    video_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    camera_angle: Mapped[str] = mapped_column(String(20), nullable=False)  # face_on / down_the_line
    club_type: Mapped[str] = mapped_column(String(20), nullable=False)
    analysis_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="full_swing", server_default="'full_swing'"
    )
    # M10-03：用户声明的目标码数（yard），供 yardage book 历史反推
    target_yardage: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # M7-14：评分管线版本标记。
    # 不做"二次评分"。
    engine_version: Mapped[str] = mapped_column(
        String(20), default="v1", server_default="'v1'", nullable=False
    )

    # 状态
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="'pending'")
    stage: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stage_progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quota_refunded: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    priority: Mapped[str] = mapped_column(String(10), default="standard", server_default="'standard'")

    # 输出
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_change: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phase_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # M10-01/02：推杆/切杆 mode 专属特征分（pendulum_stability 等）；full_swing 为 NULL
    mode_feature_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    phase_timestamps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    skeleton_video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    skeleton_data_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    share_card_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # 引擎非阻断质量提示（JSON 字符串列表），如 ["low_light","camera_shake"]
    quality_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # P2-M7-06：整体置信度 0-1（V1 引擎报告兜底 1.0；客户端 <0.5 展示「建议重拍」CTA）
    analysis_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0"
    )
    # P2-M7-06：每特征 confidence dict (feature_name → 0-1)；V1 引擎为 {}
    feature_confidences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # P2-W10：W8 引擎诊断（codec/HDR/慢动作/fps/audio/fallback），客户端调试浮层展示
    # 结构：list[{code, level, detail?, ts}]；V1 引擎或老报告为 NULL
    engine_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # 是否为示例视频体验（不计入配额、不入历史）
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 用户侧软删除：仅隐藏，不物理删；保留用于审计/溯源
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 关系
    user = relationship("User", back_populates="analyses", lazy="noload")
    issues: Mapped[list["AnalysisIssue"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    recommendations: Mapped[list["AnalysisRecommendation"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        CheckConstraint(
            "analysis_mode IN ('full_swing', 'putting', 'chipping')",
            name="chk_swing_analysis_mode",
        ),
        Index("idx_swing_analyses_user", "user_id", "created_at"),
        Index("idx_swing_analyses_status", "status"),
        Index("idx_swing_analyses_confidence", "analysis_confidence"),
        Index("idx_swing_analyses_engine_version", "engine_version"),
    )


class AnalysisIssue(Base, TimestampMixin):
    """分析报告中的问题诊断项."""

    __tablename__ = "analysis_issues"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("swing_analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    issue_type: Mapped[str] = mapped_column(String(40), nullable=False)  # casting / over_the_top ...
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)  # high / medium / low
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    key_frame_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    key_frame_timestamp: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # P2-M7-06：每诊断 confidence + tier（V1 引擎为 NULL）
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)

    analysis = relationship("SwingAnalysis", back_populates="issues", lazy="noload")

    __table_args__ = (
        Index("idx_analysis_issues_analysis", "analysis_id"),
    )


class AnalysisRecommendation(Base, TimestampMixin):
    """分析报告中的训练建议项."""

    __tablename__ = "analysis_recommendations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("swing_analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    drill_id: Mapped[str] = mapped_column(String(40), nullable=False)
    target_issue: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    analysis = relationship("SwingAnalysis", back_populates="recommendations", lazy="noload")

    __table_args__ = (
        Index("idx_analysis_recs_analysis", "analysis_id"),
    )
