"""M8-08 · 内容审核人工队列."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ModerationQueue(Base, TimestampMixin):
    __tablename__ = "moderation_queue"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    target_table: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(32), nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)
    media_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    text_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_risk_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewer_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewer_action: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "media_type IN ('image','audio','video','text')",
            name="chk_mq_media_type",
        ),
        CheckConstraint(
            "reviewer_action IS NULL OR reviewer_action IN ('approve','reject')",
            name="chk_mq_reviewer_action",
        ),
        Index("idx_mq_target", "target_table", "target_id"),
        Index("idx_mq_pending", "reviewed_at", "sla_deadline_at"),
    )
