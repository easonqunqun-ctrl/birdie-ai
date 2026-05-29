"""M13-10 · 教练-学员师生关系（M8-03 最小子集）.

revision: 0032_m13_10_coach_student_relations
down_revision: 0031_m13_09_meetup_identity
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032_m13_10_coach_student_relations"
down_revision: Union[str, None] = "0031_m13_09_meetup_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coach_student_relations",
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
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="chk_csr_status",
        ),
        sa.CheckConstraint(
            "coach_user_id != student_user_id",
            name="chk_csr_not_self",
        ),
        sa.UniqueConstraint(
            "coach_user_id",
            "student_user_id",
            name="uq_csr_coach_student",
        ),
    )
    op.create_index(
        "idx_csr_coach_status",
        "coach_student_relations",
        ["coach_user_id", "status"],
    )
    op.create_index(
        "idx_csr_student_status",
        "coach_student_relations",
        ["student_user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_csr_student_status", table_name="coach_student_relations")
    op.drop_index("idx_csr_coach_status", table_name="coach_student_relations")
    op.drop_table("coach_student_relations")
