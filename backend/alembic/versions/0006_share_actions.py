"""W7-T5: share_actions

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-21

分享行为埋点表（docs/03 §3.14）。W7 只用 share_type='report'；bonus_* 字段预留。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "share_actions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("share_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(32), nullable=True),
        sa.Column(
            "bonus_granted", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("bonus_type", sa.String(20), nullable=True),
        sa.Column("bonus_amount", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "idx_shares_user_date", "share_actions", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_shares_user_date", table_name="share_actions")
    op.drop_table("share_actions")
