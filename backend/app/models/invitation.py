"""邀请关系模型（对齐 docs/03 §3.13）."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Invitation(Base):
    """邀请关系。

    关键字段：
    - `status`：`registered`（仅注册，inviter/invitee 各 +1 分析）→ `valid`（被邀请者完成首次分析，算有效邀请）
    - `inviter_bonus_type/amount/granted`：达到阈值后发放会员天数奖励时的流水（W7 主要记录 +7 天的一次性奖励）
    """

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # inv_<nanoid>
    inviter_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    invitee_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    invite_code: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="registered", server_default="'registered'"
    )

    inviter_bonus_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    inviter_bonus_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bonus_granted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    bonus_granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )

    __table_args__ = (
        UniqueConstraint("inviter_id", "invitee_id", name="uq_invitation"),
        CheckConstraint(
            "status IN ('registered', 'valid')",
            name="chk_invitation_status",
        ),
        Index("idx_invitations_inviter", "inviter_id", "created_at"),
        Index("idx_invitations_invitee", "invitee_id"),
    )
