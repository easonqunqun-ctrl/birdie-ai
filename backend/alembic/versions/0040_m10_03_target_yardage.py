"""M10-03 · swing_analyses.target_yardage 列（yardage book 反推采样）.

revision: 0040_m10_03_target_yardage
down_revision: 0039_m10_01_analysis_mode
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040_m10_03_target_yardage"
down_revision: Union[str, None] = "0039_m10_01_analysis_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "swing_analyses",
        sa.Column("target_yardage", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("swing_analyses", "target_yardage")
