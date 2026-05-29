"""M8-01 · coach_profiles + coach_verifications.

revision: 0033_m8_01_coach_profiles
down_revision: 0032_m13_10_coach_student_relations
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0033_m8_01_coach_profiles"
down_revision: Union[str, None] = "0032_m13_10_coach_student_relations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coach_profiles",
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.String(length=60), nullable=False),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column(
            "certifications",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "specialties",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "service_cities",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending', 'active', 'rejected', 'paused')",
            name="chk_cp_status",
        ),
        sa.CheckConstraint(
            "level IN ('pga', 'china_pga', 'regional', 'club_pro')",
            name="chk_cp_level",
        ),
    )
    op.create_index(
        "idx_cp_status",
        "coach_profiles",
        ["status", "applied_at"],
    )

    op.create_table(
        "coach_verifications",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "materials",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "reviewer_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
            "review_status IN ('pending', 'approved', 'rejected', 'need_more')",
            name="chk_cv_status",
        ),
    )
    op.create_index(
        "idx_cv_status_submitted",
        "coach_verifications",
        ["review_status", "submitted_at"],
    )
    op.create_index(
        "idx_cv_user",
        "coach_verifications",
        ["user_id", "submitted_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_cv_user", table_name="coach_verifications")
    op.drop_index("idx_cv_status_submitted", table_name="coach_verifications")
    op.drop_table("coach_verifications")
    op.drop_index("idx_cp_status", table_name="coach_profiles")
    op.drop_table("coach_profiles")
