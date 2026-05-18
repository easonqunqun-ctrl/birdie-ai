"""users.papay_contract_id：微信委托代扣签约成功后的协议号."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_user_papay_contract_id"
down_revision: Union[str, None] = "0013_has_completed_real_analysis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("papay_contract_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "papay_contract_id")
