"""M8-03 · 教练-学员双向 opt-in 绑定扩展.

revision: 0034_m8_03_coach_student_binding
down_revision: 0033_m8_01_coach_profiles
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0034_m8_03_coach_student_binding"
down_revision: str | None = "0033_m8_01_coach_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "coach_student_relations",
        sa.Column(
            "visibility_payload",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "coach_student_relations",
        sa.Column(
            "invited_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "coach_student_relations",
        sa.Column("invite_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "coach_student_relations",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "coach_student_relations",
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "coach_student_relations",
        sa.Column(
            "ended_by_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("coach_student_relations", sa.Column("pause_reason", sa.Text(), nullable=True))
    op.add_column("coach_student_relations", sa.Column("notes", sa.Text(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE coach_student_relations
            SET status = 'ended', ended_at = updated_at
            WHERE status = 'inactive'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE coach_student_relations
            SET invited_at = created_at, accepted_at = created_at
            WHERE status = 'active'
            """
        )
    )

    op.drop_constraint("uq_csr_coach_student", "coach_student_relations", type_="unique")
    op.drop_constraint("chk_csr_status", "coach_student_relations", type_="check")

    op.alter_column(
        "coach_student_relations",
        "status",
        existing_type=sa.String(length=16),
        type_=sa.String(length=20),
        existing_nullable=False,
    )

    op.create_check_constraint(
        "chk_csr_status",
        "coach_student_relations",
        "status IN ('pending', 'active', 'paused', 'ended')",
    )
    op.create_index(
        "uq_csr_pending_active",
        "coach_student_relations",
        ["coach_user_id", "student_user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'active')"),
    )

    op.alter_column(
        "coach_student_relations",
        "invited_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


def downgrade() -> None:
    op.drop_index("uq_csr_pending_active", table_name="coach_student_relations")
    op.drop_constraint("chk_csr_status", "coach_student_relations", type_="check")

    op.execute(
        sa.text(
            """
            UPDATE coach_student_relations
            SET status = 'inactive'
            WHERE status IN ('pending', 'paused', 'ended')
            """
        )
    )

    op.create_check_constraint(
        "chk_csr_status",
        "coach_student_relations",
        "status IN ('active', 'inactive')",
    )
    op.create_unique_constraint(
        "uq_csr_coach_student",
        "coach_student_relations",
        ["coach_user_id", "student_user_id"],
    )

    op.alter_column(
        "coach_student_relations",
        "status",
        existing_type=sa.String(length=20),
        type_=sa.String(length=16),
        existing_nullable=False,
    )

    op.drop_column("coach_student_relations", "notes")
    op.drop_column("coach_student_relations", "pause_reason")
    op.drop_column("coach_student_relations", "ended_by_user_id")
    op.drop_column("coach_student_relations", "ended_at")
    op.drop_column("coach_student_relations", "accepted_at")
    op.drop_column("coach_student_relations", "invite_message")
    op.drop_column("coach_student_relations", "invited_at")
    op.drop_column("coach_student_relations", "visibility_payload")
