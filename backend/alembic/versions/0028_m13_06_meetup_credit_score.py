"""M13-06 · users.meetup_credit_score（约球信用分 0-100）."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_m13_06_meetup_credit_score"
down_revision: Union[str, None] = "0027_m12_10_pro_favorites_try_it"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "meetup_credit_score",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
    )
    op.create_check_constraint(
        "chk_users_meetup_credit_score",
        "users",
        "meetup_credit_score BETWEEN 0 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint("chk_users_meetup_credit_score", "users", type_="check")
    op.drop_column("users", "meetup_credit_score")
