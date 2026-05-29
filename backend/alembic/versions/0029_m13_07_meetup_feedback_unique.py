"""M13-07 · meetup_feedbacks 唯一约束 + credit_delta 范围放宽."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_m13_07_meetup_feedback_unique"
down_revision: Union[str, None] = "0028_m13_06_meetup_credit_score"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("chk_mfb_credit_delta", "meetup_feedbacks", type_="check")
    op.create_check_constraint(
        "chk_mfb_credit_delta",
        "meetup_feedbacks",
        "credit_delta BETWEEN -20 AND 20",
    )
    op.create_unique_constraint(
        "uq_mfb_invitation_reviewer",
        "meetup_feedbacks",
        ["invitation_id", "reviewer_user_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_mfb_invitation_reviewer", "meetup_feedbacks", type_="unique")
    op.drop_constraint("chk_mfb_credit_delta", "meetup_feedbacks", type_="check")
    op.create_check_constraint(
        "chk_mfb_credit_delta",
        "meetup_feedbacks",
        "credit_delta BETWEEN -10 AND 10",
    )
