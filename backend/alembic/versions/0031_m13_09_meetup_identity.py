"""M13-09 · 约球实名 / 年龄 / 性别字段.

revision: 0031_m13_09_meetup_identity
down_revision: 0030_m13_08_event_participation_score
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_m13_09_meetup_identity"
down_revision: Union[str, None] = "0030_m13_08_event_participation_score"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column(
        "users",
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("gender", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "chk_users_gender",
        "users",
        "gender IS NULL OR gender IN ('female', 'male', 'other')",
    )


def downgrade() -> None:
    op.drop_constraint("chk_users_gender", "users", type_="check")
    op.drop_column("users", "gender")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "birth_date")
