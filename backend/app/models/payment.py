"""支付相关模型（对齐 docs/03-数据库设计文档.md §3.11-3.12）.

W7-T1：订单与支付流水。MVP 阶段 `WECHAT_PAY_MOCK_MODE=True` 走 mock，
真实微信支付在 W8 商户号落地后接入；`wechat_prepay_id / wechat_transaction_id`
字段已预留，结构与真实场景 1:1 对齐。
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Order(Base, TimestampMixin):
    """会员订单."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # ord_<nanoid>
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 套餐 & 金额
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)  # monthly/yearly/family
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 分
    currency: Mapped[str] = mapped_column(String(3), default="CNY", server_default="'CNY'")

    # 状态
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="'pending'")
    # pending / paid / failed / refunded / cancelled

    # 微信支付（mock 模式下不填）
    wechat_prepay_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wechat_transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 会员期间（paid 后写入）
    membership_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    membership_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refund_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "plan_type IN ('monthly', 'yearly', 'family')",
            name="chk_order_plan",
        ),
        CheckConstraint(
            "status IN ('pending', 'paid', 'failed', 'refunded', 'cancelled')",
            name="chk_order_status",
        ),
        Index("idx_orders_user", "user_id", "created_at"),
        Index(
            "idx_orders_pending",
            "status",
            postgresql_where="status = 'pending'",
        ),
        Index(
            "idx_orders_wechat",
            "wechat_transaction_id",
            postgresql_where="wechat_transaction_id IS NOT NULL",
        ),
    )


class PaymentTransaction(Base):
    """支付流水（微信回调原样存档；mock 模式只记 mock:true）."""

    __tablename__ = "payment_transactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)  # payment / refund
    amount: Mapped[int] = mapped_column(Integer, nullable=False)

    wechat_notify_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="NOW()",
    )

    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('payment', 'refund')",
            name="chk_txn_type",
        ),
        Index("idx_txn_order", "order_id"),
        Index("idx_txn_user", "user_id", "created_at"),
    )
