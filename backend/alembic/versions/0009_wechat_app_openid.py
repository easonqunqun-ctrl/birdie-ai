"""W10-RN：双端微信标识（小程序 openid + App openid + unionid 合并）

小程序 openid 列 `wechat_openid` 改为可空；纯 App 用户仅填 `wechat_app_openid`。
PostgreSQL UNIQUE 允许多行 NULL：改为部分唯一索引，避免重复空值。
."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_wechat_app_openid"
down_revision: Union[str, None] = "0008_account_deletion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_users_openid", "users", type_="unique")
    op.drop_index("idx_users_openid", table_name="users")

    op.alter_column(
        "users",
        "wechat_openid",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    op.add_column(
        "users",
        sa.Column("wechat_app_openid", sa.String(length=64), nullable=True),
    )

    op.create_index(
        "uq_users_wechat_openid_nn",
        "users",
        ["wechat_openid"],
        unique=True,
        postgresql_where=sa.text("wechat_openid IS NOT NULL"),
    )
    op.create_index(
        "uq_users_wechat_app_openid_nn",
        "users",
        ["wechat_app_openid"],
        unique=True,
        postgresql_where=sa.text("wechat_app_openid IS NOT NULL"),
    )
    op.create_index(
        "idx_users_unionid_nn",
        "users",
        ["wechat_unionid"],
        unique=False,
        postgresql_where=sa.text("wechat_unionid IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_check_constraint(
        "ck_users_wechat_oid_present",
        "users",
        sa.text("(wechat_openid IS NOT NULL OR wechat_app_openid IS NOT NULL)"),
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_wechat_oid_present", "users", type_="check")
    op.drop_index("idx_users_unionid_nn", table_name="users")
    op.drop_index("uq_users_wechat_app_openid_nn", table_name="users")
    op.drop_index("uq_users_wechat_openid_nn", table_name="users")

    op.drop_column("users", "wechat_app_openid")
    op.alter_column(
        "users",
        "wechat_openid",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.create_unique_constraint("uq_users_openid", "users", ["wechat_openid"])
    op.create_index("idx_users_openid", "users", ["wechat_openid"])
