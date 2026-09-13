"""停发前 100 名欢迎包；改为注册起 3 个月免费。

Revision ID: 0047_clear_welcome
Revises: 0046_user_market
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047_clear_welcome"
down_revision: Union[str, None] = "0046_user_market"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE users SET intl_welcome_granted = false, "
            "intl_welcome_remaining = 0 "
            "WHERE intl_welcome_granted IS TRUE"
        )
    )


def downgrade() -> None:
    pass
