"""挥杆分析相关模型（对齐 docs/03-数据库设计文档.md 3.2-3.4 节）."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
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
    phase_timestamps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    skeleton_video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    skeleton_data_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    share_card_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

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
        Index("idx_swing_analyses_user", "user_id", "created_at"),
        Index("idx_swing_analyses_status", "status"),
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
