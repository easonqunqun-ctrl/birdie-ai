"""M8-07 · course_session_recaps 表.

revision: 0036_m8_07_course_session_recaps
down_revision: 0035_m8_05_coach_assigned_tasks
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0036_m8_07_course_session_recaps"
down_revision: str | None = "0035_m8_05_coach_assigned_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_session_recaps",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "coach_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column(
            "student_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "analysis_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("ai_summary_model", sa.String(length=32), nullable=True),
        sa.Column("coach_manual_notes", sa.Text(), nullable=True),
        sa.Column("pdf_object_key", sa.String(length=512), nullable=True),
        sa.Column("pdf_url_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="draft",
        ),
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
            "status IN ('draft', 'finalized', 'exported')",
            name="chk_recap_status",
        ),
    )
    op.create_index(
        "idx_recap_coach_date",
        "course_session_recaps",
        ["coach_user_id", "session_date"],
    )


def downgrade() -> None:
    op.drop_index("idx_recap_coach_date", table_name="course_session_recaps")
    op.drop_table("course_session_recaps")
