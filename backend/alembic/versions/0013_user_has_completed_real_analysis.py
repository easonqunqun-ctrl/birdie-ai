"""users.has_completed_real_analysis：首次非示例分析完成后隐藏示例入口（O-03）."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_has_completed_real_analysis"
down_revision: Union[str, None] = "0012_ver_num_w128"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "has_completed_real_analysis",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute(
        """
        UPDATE users
        SET has_completed_real_analysis = true
        WHERE id IN (
            SELECT DISTINCT user_id
            FROM swing_analyses
            WHERE is_sample IS false
              AND status = 'completed'
              AND deleted_at IS NULL
        )
        """
    )


def downgrade() -> None:
    op.drop_column("users", "has_completed_real_analysis")
