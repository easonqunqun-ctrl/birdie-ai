"""App Sign in with Apple：users.apple_sub + 身份约束放宽

Revision ID: 0045_apple_sub
Revises: 0044_m10_04_drill_w26_tips_full
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045_apple_sub"
down_revision: Union[str, None] = "0044_m10_04_drill_w26_tips_full"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("apple_sub", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "uq_users_apple_sub_nn",
        "users",
        ["apple_sub"],
        unique=True,
        postgresql_where=sa.text("apple_sub IS NOT NULL"),
    )
    op.drop_constraint("ck_users_wechat_oid_present", "users", type_="check")
    op.create_check_constraint(
        "ck_users_identity_present",
        "users",
        sa.text(
            "(wechat_openid IS NOT NULL OR wechat_app_openid IS NOT NULL "
            "OR apple_sub IS NOT NULL)"
        ),
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_identity_present", "users", type_="check")
    op.create_check_constraint(
        "ck_users_wechat_oid_present",
        "users",
        sa.text("(wechat_openid IS NOT NULL OR wechat_app_openid IS NOT NULL)"),
    )
    op.drop_index("uq_users_apple_sub_nn", table_name="users")
    op.drop_column("users", "apple_sub")
