"""swing_analyses.quality_warnings：引擎非阻断质量提示（ENG-02）."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_swing_analysis_quality_warnings"
down_revision: Union[str, None] = "0014_user_papay_contract_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "swing_analyses",
        sa.Column(
            "quality_warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("swing_analyses", "quality_warnings")
