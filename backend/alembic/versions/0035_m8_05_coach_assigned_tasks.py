"""M8-05 · coach_assigned_tasks 表.

revision: 0035_m8_05_coach_assigned_tasks
down_revision: 0034_m8_03_coach_student_binding
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035_m8_05_coach_assigned_tasks"
down_revision: Union[str, None] = "0034_m8_03_coach_student_binding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coach_assigned_tasks",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "coach_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relation_id",
            sa.String(length=32),
            sa.ForeignKey("coach_student_relations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column(
            "drill_id",
            sa.String(length=32),
            sa.ForeignKey("drills.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("target_week", sa.Date(), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("target_issue", sa.String(length=64), nullable=True),
        sa.Column("coach_note", sa.Text(), nullable=True),
        sa.Column(
            "training_task_id",
            sa.String(length=32),
            sa.ForeignKey("training_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="assigned",
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "source_type IN ('drill', 'custom_video')",
            name="chk_cat_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('assigned', 'started', 'done', 'expired')",
            name="chk_cat_status",
        ),
        sa.CheckConstraint(
            "target_count >= 1 AND target_count <= 99",
            name="chk_cat_target_count",
        ),
    )
    op.create_index(
        "idx_cat_student_week",
        "coach_assigned_tasks",
        ["student_user_id", "target_week"],
    )
    op.create_index(
        "idx_cat_coach_created",
        "coach_assigned_tasks",
        ["coach_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_cat_coach_created", table_name="coach_assigned_tasks")
    op.drop_index("idx_cat_student_week", table_name="coach_assigned_tasks")
    op.drop_table("coach_assigned_tasks")
