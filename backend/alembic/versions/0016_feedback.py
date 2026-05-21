"""feedbacks 表：用户意见反馈（docs/02 §2.6）.

revision: 0016_feedback
down_revision: 0015_swing_analysis_quality_warnings
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_feedback"
down_revision: Union[str, None] = "0015_swing_analysis_quality_warnings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("contact", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "char_length(content) >= 1 AND char_length(content) <= 500",
            name="chk_feedback_content_len",
        ),
    )
    op.create_index(
        "idx_feedbacks_user_created_at",
        "feedbacks",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_feedbacks_created_at",
        "feedbacks",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_feedbacks_created_at", table_name="feedbacks")
    op.drop_index("idx_feedbacks_user_created_at", table_name="feedbacks")
    op.drop_table("feedbacks")
