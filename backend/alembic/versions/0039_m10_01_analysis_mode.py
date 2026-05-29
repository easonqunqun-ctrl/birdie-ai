"""M10-01 · swing_analyses.analysis_mode 列.

revision: 0039_m10_01_analysis_mode
down_revision: 0038_m8_10_coach_seed_level
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039_m10_01_analysis_mode"
down_revision: Union[str, None] = "0038_m8_10_coach_seed_level"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "swing_analyses",
        sa.Column(
            "analysis_mode",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'full_swing'"),
        ),
    )
    op.add_column(
        "swing_analyses",
        sa.Column("mode_feature_scores", sa.dialects.postgresql.JSONB(), nullable=True),
    )
    op.create_check_constraint(
        "chk_swing_analysis_mode",
        "swing_analyses",
        "analysis_mode IN ('full_swing', 'putting', 'chipping')",
    )


def downgrade() -> None:
    op.drop_constraint("chk_swing_analysis_mode", "swing_analyses", type_="check")
    op.drop_column("swing_analyses", "mode_feature_scores")
    op.drop_column("swing_analyses", "analysis_mode")
