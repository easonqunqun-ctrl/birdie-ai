"""AI 对话相关模型."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ChatQuota(Base, TimestampMixin):
    """每日对话配额."""

    __tablename__ = "chat_quotas"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    quota_date: Mapped[date] = mapped_column(Date, nullable=False)
    used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total: Mapped[int] = mapped_column(Integer, default=5, server_default="5")  # -1 = 无限

    __table_args__ = (
        UniqueConstraint("user_id", "quota_date", name="uq_chat_quota"),
        Index("idx_chat_quotas_lookup", "user_id", "quota_date"),
    )


class ChatSession(Base, TimestampMixin):
    """对话会话."""

    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    context_analysis_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("swing_analyses.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    system_prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        Index("idx_chat_sessions_user", "user_id", "last_message_at"),
    )


class ChatMessage(Base, TimestampMixin):
    """对话消息."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / assistant / system
    content: Mapped[str] = mapped_column(String(4000), nullable=False)
    attachments: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session = relationship("ChatSession", back_populates="messages", lazy="noload")

    __table_args__ = (
        Index("idx_chat_messages_session", "session_id", "created_at"),
    )
