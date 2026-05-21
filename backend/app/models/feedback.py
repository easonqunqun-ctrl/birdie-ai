"""用户意见反馈模型（对齐 docs/02 §2.6 + docs/03 feedbacks 表）.

设计取舍
--------
- 仅记登录用户反馈：未登录态没有业务入口能触发到这里（profile 菜单需先登录）
- `content` 限 1-500 字符，**500 是产品上限**；服务层做硬截断 + 计数上报
- `contact` 选填：手机号 / 邮箱 / 微信号都允许，运营人工识别
- 同一用户**反垃圾**：服务层在 60 秒内拒绝同用户重复提交（详见 service）
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # fb_<nanoid>
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    contact: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(content) >= 1 AND char_length(content) <= 500",
            name="chk_feedback_content_len",
        ),
        Index("idx_feedbacks_user_created_at", "user_id", "created_at"),
        Index("idx_feedbacks_created_at", "created_at"),
    )
