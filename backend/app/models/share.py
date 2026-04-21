"""分享行为记录模型（W7-T5，对齐 docs/03 §3.14）.

场景：
- `share_type`：`report`（分享报告卡片到聊天）/ `invite_poster`（W8 海报）/ `moments`（朋友圈，延后）
- `target_id`：report 场景下 = analysis_id；invite 场景下 = invite_code
- `bonus_granted`：W7 暂不给分享奖励（防刷量），字段预留；后续每日首次分享可 +1 次对话
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ShareAction(Base):
    __tablename__ = "share_actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    share_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    bonus_granted: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )
    bonus_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bonus_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )

    __table_args__ = (
        Index("idx_shares_user_date", "user_id", "created_at"),
    )
