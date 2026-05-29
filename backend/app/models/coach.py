"""M8-01 / M8-04 / M12-09 · 教练数据模型."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CoachProfile(Base, TimestampMixin):
    """教练公开档案（M8-01）；与 users 1:1."""

    __tablename__ = "coach_profiles"

    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(String(60), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    certifications: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    specialties: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    service_cities: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="'pending'"
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'rejected', 'paused')",
            name="chk_cp_status",
        ),
        CheckConstraint(
            "level IN ('pga', 'china_pga', 'regional', 'club_pro')",
            name="chk_cp_level",
        ),
        Index("idx_cp_status", "status", "applied_at"),
    )


class CoachVerification(Base, TimestampMixin):
    """教练资质审核记录（M8-01）；每次申请独立一行."""

    __tablename__ = "coach_verifications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )
    materials: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="'pending'"
    )
    reviewer_user_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default="{}",
    )

    __table_args__ = (
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected', 'need_more')",
            name="chk_cv_status",
        ),
        Index("idx_cv_status_submitted", "review_status", "submitted_at"),
        Index("idx_cv_user", "user_id", "submitted_at"),
    )


class AnalysisAnnotation(Base, TimestampMixin):
    """教练在学员分析报告上的批注."""

    __tablename__ = "analysis_annotations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    coach_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("swing_analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    annotation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    pro_clip_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("pro_swing_clips.id", ondelete="SET NULL"),
        nullable=True,
    )
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="approved"
    )
    is_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    __table_args__ = (
        Index("idx_ann_analysis_visible", "analysis_id", "is_visible"),
        Index("idx_ann_coach", "coach_user_id", "created_at"),
    )


class CoachStudentRelation(Base, TimestampMixin):
    """教练-学员绑定（M8-03 最小子集；M13-10 旁观守门）."""

    __tablename__ = "coach_student_relations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    coach_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="'active'"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="chk_csr_status",
        ),
        CheckConstraint(
            "coach_user_id != student_user_id",
            name="chk_csr_not_self",
        ),
        UniqueConstraint(
            "coach_user_id",
            "student_user_id",
            name="uq_csr_coach_student",
        ),
        Index("idx_csr_coach_status", "coach_user_id", "status"),
        Index("idx_csr_student_status", "student_user_id", "status"),
    )
