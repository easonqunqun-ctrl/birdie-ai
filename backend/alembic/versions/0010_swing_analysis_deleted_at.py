"""挥杆分析报告用户侧软删除：swing_analyses.deleted_at"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_swing_analysis_deleted_at"
down_revision: Union[str, None] = "0009_wechat_app_openid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "swing_analyses",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("swing_analyses", "deleted_at")
