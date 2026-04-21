"""W7-T4: invitations

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-21

邀请裂变：`invitations` 表对齐 docs/03 §3.13。
（用户表本身已有 `invite_code` / `invited_by_user_id` 字段，M1 时已落；这里仅补关系表。）
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "inviter_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invitee_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("invite_code", sa.String(8), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="'registered'"
        ),
        sa.Column("inviter_bonus_type", sa.String(20), nullable=True),
        sa.Column("inviter_bonus_amount", sa.Integer, nullable=True),
        sa.Column(
            "bonus_granted", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("bonus_granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("inviter_id", "invitee_id", name="uq_invitation"),
        sa.CheckConstraint(
            "status IN ('registered', 'valid')",
            name="chk_invitation_status",
        ),
    )
    op.create_index(
        "idx_invitations_inviter", "invitations", ["inviter_id", "created_at"]
    )
    op.create_index("idx_invitations_invitee", "invitations", ["invitee_id"])


def downgrade() -> None:
    op.drop_index("idx_invitations_invitee", table_name="invitations")
    op.drop_index("idx_invitations_inviter", table_name="invitations")
    op.drop_table("invitations")
