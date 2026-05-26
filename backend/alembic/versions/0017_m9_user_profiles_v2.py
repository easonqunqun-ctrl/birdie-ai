"""M9 P2-M9-01 user_profiles_v2 + user_clubs 数据模型.

逻辑编号：docs/03 §8.7 规划 0008（M9 首个迁移）；实际落库编号：0017（按 alembic
head 续编，head=0016_feedback）。docs/03 §8.7 在 docs/23 收尾合并后会回流。

revision: 0017_m9_user_profiles_v2
down_revision: 0016_feedback
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_m9_user_profiles_v2"
down_revision: Union[str, None] = "0016_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles_v2",
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("handicap_official", sa.Numeric(4, 1), nullable=True),
        sa.Column("handicap_self", sa.Numeric(4, 1), nullable=True),
        sa.Column("handicap_source", sa.String(length=20), nullable=True),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Integer(), nullable=True),
        sa.Column("handedness", sa.String(length=10), nullable=True),
        sa.Column(
            "known_injuries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "mid_long_goals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("training_preference", sa.String(length=20), nullable=True),
        sa.Column("weekly_target_sessions", sa.Integer(), nullable=True),
        sa.Column(
            "favorite_course_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "privacy_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "coach_visible_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
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
            "handedness IS NULL OR handedness IN ('right', 'left', 'switch')",
            name="chk_user_profiles_v2_handedness",
        ),
        sa.CheckConstraint(
            "handicap_official IS NULL OR (handicap_official BETWEEN -10 AND 54)",
            name="chk_user_profiles_v2_handicap_official",
        ),
        sa.CheckConstraint(
            "handicap_self IS NULL OR (handicap_self BETWEEN -10 AND 54)",
            name="chk_user_profiles_v2_handicap_self",
        ),
        sa.CheckConstraint(
            "handicap_source IS NULL OR handicap_source IN ('rcga', 'usga', 'self')",
            name="chk_user_profiles_v2_handicap_source",
        ),
        sa.CheckConstraint(
            "training_preference IS NULL OR training_preference IN ('video', 'text', 'mixed')",
            name="chk_user_profiles_v2_training_preference",
        ),
        sa.CheckConstraint(
            "height_cm IS NULL OR (height_cm BETWEEN 100 AND 250)",
            name="chk_user_profiles_v2_height_cm",
        ),
        sa.CheckConstraint(
            "weight_kg IS NULL OR (weight_kg BETWEEN 30 AND 200)",
            name="chk_user_profiles_v2_weight_kg",
        ),
        sa.CheckConstraint(
            "weekly_target_sessions IS NULL OR (weekly_target_sessions BETWEEN 0 AND 14)",
            name="chk_user_profiles_v2_weekly_target_sessions",
        ),
    )
    op.create_index(
        "idx_user_profiles_v2_updated_at",
        "user_profiles_v2",
        ["updated_at"],
    )

    op.create_table(
        "user_clubs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("club_type", sa.String(length=20), nullable=False),
        sa.Column("nickname", sa.String(length=40), nullable=True),
        sa.Column("self_yardage_m", sa.Integer(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
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
            "self_yardage_m IS NULL OR (self_yardage_m BETWEEN 0 AND 400)",
            name="chk_user_clubs_self_yardage_m",
        ),
    )
    op.create_index("idx_user_clubs_user_id", "user_clubs", ["user_id"])
    op.create_index(
        "idx_user_clubs_user_active",
        "user_clubs",
        ["user_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("idx_user_clubs_user_active", table_name="user_clubs")
    op.drop_index("idx_user_clubs_user_id", table_name="user_clubs")
    op.drop_table("user_clubs")
    op.drop_index("idx_user_profiles_v2_updated_at", table_name="user_profiles_v2")
    op.drop_table("user_profiles_v2")
