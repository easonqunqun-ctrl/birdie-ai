"""M13-08 · 挑战赛成绩 payload + 报名唯一约束.

revision: 0030_m13_08_event_participation_score
down_revision: 0029_m13_07_meetup_feedback_unique
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_m13_08_event_participation_score"
down_revision: Union[str, None] = "0029_m13_07_meetup_feedback_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event_participations",
        sa.Column(
            "score_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_unique_constraint(
        "uq_evp_event_user",
        "event_participations",
        ["event_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_evp_event_user", "event_participations", type_="unique")
    op.drop_column("event_participations", "score_payload")
