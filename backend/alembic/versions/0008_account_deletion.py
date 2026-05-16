"""users 表增加 account_deletion_scheduled_at（MVP §3.4 注销冷静期）."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_account_deletion"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "account_deletion_scheduled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_users_deletion_due",
        "users",
        ["account_deletion_scheduled_at"],
        postgresql_where=sa.text("account_deletion_scheduled_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_deletion_due", table_name="users")
    op.drop_column("users", "account_deletion_scheduled_at")
