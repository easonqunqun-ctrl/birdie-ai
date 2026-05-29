"""M8-08 · moderation_queue 表.

revision: 0037_m8_08_moderation_queue
down_revision: 0036_m8_07_course_session_recaps
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0037_m8_08_moderation_queue"
down_revision: str | None = "0036_m8_07_course_session_recaps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "moderation_queue",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("target_table", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=32), nullable=False),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column("media_url", sa.String(length=512), nullable=True),
        sa.Column("text_snapshot", sa.Text(), nullable=True),
        sa.Column("ai_risk_label", sa.String(length=64), nullable=True),
        sa.Column("ai_risk_score", sa.Float(), nullable=True),
        sa.Column("ai_decision", sa.String(length=20), nullable=True),
        sa.Column("reviewer_user_id", sa.String(length=32), nullable=True),
        sa.Column("reviewer_action", sa.String(length=20), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "media_type IN ('image','audio','video','text')",
            name="chk_mq_media_type",
        ),
        sa.CheckConstraint(
            "reviewer_action IS NULL OR reviewer_action IN ('approve','reject')",
            name="chk_mq_reviewer_action",
        ),
    )
    op.create_index("idx_mq_target", "moderation_queue", ["target_table", "target_id"])
    op.create_index(
        "idx_mq_pending",
        "moderation_queue",
        ["reviewed_at", "sla_deadline_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_mq_pending", table_name="moderation_queue")
    op.drop_index("idx_mq_target", table_name="moderation_queue")
    op.drop_table("moderation_queue")
