"""M7-14 swing_analyses.engine_version 列 + 索引.

逻辑编号：docs/03 §8.7 规划 0007；实际落库编号：0021
（按 alembic head 续编：head=0016_feedback, M9-01=0017, M11-01=0018,
M12-01=0019, M13-01=0020 → 0021）。

revision: 0021_swing_analyses_engine_version
down_revision: 0020_m13_meetup_schema
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_swing_analyses_engine_version"
down_revision: Union[str, None] = "0020_m13_meetup_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "swing_analyses",
        sa.Column(
            "engine_version",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'v1'"),
        ),
    )
    op.create_index(
        "idx_swing_analyses_engine_version",
        "swing_analyses",
        ["engine_version"],
    )


def downgrade() -> None:
    op.drop_index("idx_swing_analyses_engine_version", table_name="swing_analyses")
    op.drop_column("swing_analyses", "engine_version")
