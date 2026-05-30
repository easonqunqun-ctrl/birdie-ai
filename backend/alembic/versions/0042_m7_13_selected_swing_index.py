"""M7-13 · swing_analyses.selected_swing_index（多挥选段）.

revision: 0042_m7_13_selected_swing_index
down_revision: 0041_m10_04_drill_category
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042_m7_13_selected_swing_index"
down_revision: Union[str, None] = "0041_m10_04_drill_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "swing_analyses",
        sa.Column("selected_swing_index", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("swing_analyses", "selected_swing_index")
