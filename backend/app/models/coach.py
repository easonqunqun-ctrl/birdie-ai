"""M8-04 / M12-09 · 教练报告批注（MVP：video_ref 引用职业镜头）."""

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


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
