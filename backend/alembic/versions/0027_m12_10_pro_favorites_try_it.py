"""M12-10 · user_pro_favorites.training_task_id（想试试看任务关联）."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_m12_10_pro_favorites_try_it"
down_revision: Union[str, None] = "0026_m8_analysis_annotations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_pro_favorites",
        sa.Column(
            "training_task_id",
            sa.String(length=32),
            sa.ForeignKey("training_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_upf_training_task",
        "user_pro_favorites",
        ["training_task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_upf_training_task", table_name="user_pro_favorites")
    op.drop_column("user_pro_favorites", "training_task_id")
