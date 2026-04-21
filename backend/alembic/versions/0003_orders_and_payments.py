"""W7-T1: orders + payment_transactions

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-21

W7 商业化链路：会员订单 + 支付流水。对齐 docs/03 §3.11-3.12。

设计要点：
- `orders` 的 `wechat_prepay_id` / `wechat_transaction_id` 字段在 mock 模式下保持 NULL；
  W8 接真实商户号时通过 `UPDATE orders SET wechat_transaction_id=?` 回写
- `payment_transactions` 保存微信回调原始 JSON（审计 + 重放）；mock 模式存 {"mock": true}
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ==================== orders ====================
    op.create_table(
        "orders",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="'CNY'"),
        sa.Column("status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("wechat_prepay_id", sa.String(128), nullable=True),
        sa.Column("wechat_transaction_id", sa.String(64), nullable=True),
        sa.Column("membership_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("membership_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refund_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "plan_type IN ('monthly', 'yearly', 'family')",
            name="chk_order_plan",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'failed', 'refunded', 'cancelled')",
            name="chk_order_status",
        ),
    )
    op.create_index("idx_orders_user", "orders", ["user_id", "created_at"])
    op.create_index(
        "idx_orders_pending",
        "orders",
        ["status"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "idx_orders_wechat",
        "orders",
        ["wechat_transaction_id"],
        postgresql_where=sa.text("wechat_transaction_id IS NOT NULL"),
    )

    # ==================== payment_transactions ====================
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "order_id",
            sa.String(32),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("wechat_notify_data", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "transaction_type IN ('payment', 'refund')",
            name="chk_txn_type",
        ),
    )
    op.create_index("idx_txn_order", "payment_transactions", ["order_id"])
    op.create_index("idx_txn_user", "payment_transactions", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_txn_user", table_name="payment_transactions")
    op.drop_index("idx_txn_order", table_name="payment_transactions")
    op.drop_table("payment_transactions")

    op.drop_index("idx_orders_wechat", table_name="orders")
    op.drop_index("idx_orders_pending", table_name="orders")
    op.drop_index("idx_orders_user", table_name="orders")
    op.drop_table("orders")
