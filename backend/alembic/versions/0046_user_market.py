"""users.market + 各市场前 100 名欢迎包

Revision ID: 0046_user_market
Revises: 0045_apple_sub
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0046_user_market"
down_revision: Union[str, None] = "0045_apple_sub"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("market", sa.String(length=8), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "intl_welcome_granted",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "intl_welcome_remaining",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "chk_users_market",
        "users",
        "market IS NULL OR market IN ('cn', 'intl')",
    )
    op.create_check_constraint(
        "chk_users_intl_welcome_remaining",
        "users",
        "intl_welcome_remaining >= 0",
    )
    op.create_index(
        "idx_users_intl_welcome_granted",
        "users",
        ["intl_welcome_granted"],
        postgresql_where=sa.text("intl_welcome_granted IS TRUE"),
    )
    op.execute(
        sa.text(
            "UPDATE users SET market = 'cn' "
            "WHERE market IS NULL AND ("
            "wechat_openid IS NOT NULL OR wechat_app_openid IS NOT NULL)"
        )
    )
    # 各市场按注册时间最早的 100 人发放欢迎包（docs/01 §2.2.1）
    op.execute(
        sa.text(
            """
            WITH ranked AS (
              SELECT id,
                     ROW_NUMBER() OVER (
                       PARTITION BY market
                       ORDER BY created_at ASC NULLS LAST, id ASC
                     ) AS rn
              FROM users
              WHERE deleted_at IS NULL
                AND market IN ('cn', 'intl')
            )
            UPDATE users AS u
            SET intl_welcome_granted = true,
                intl_welcome_remaining = 100
            FROM ranked AS r
            WHERE u.id = r.id AND r.rn <= 100
            """
        )
    )


def downgrade() -> None:
    op.drop_index("idx_users_intl_welcome_granted", table_name="users")
    op.drop_constraint("chk_users_intl_welcome_remaining", "users", type_="check")
    op.drop_constraint("chk_users_market", "users", type_="check")
    op.drop_column("users", "intl_welcome_remaining")
    op.drop_column("users", "intl_welcome_granted")
    op.drop_column("users", "market")
