"""M12 P2-M12-01 球手对比库 6 张表.

逻辑编号：docs/03 §8.7 规划 0009；实际落库编号：0019（按 alembic head 续编：
head=0016_feedback，M9-01=0017，M11-01=0018 → 0019）。

revision: 0019_m12_pro_library_schema
down_revision: 0018_m11_courses_schema
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_m12_pro_library_schema"
down_revision: Union[str, None] = "0018_m11_courses_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- pro_players ----------
    op.create_table(
        "pro_players",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("name_en", sa.String(length=80), nullable=True),
        sa.Column("nationality", sa.String(length=3), nullable=True),
        sa.Column("handedness", sa.String(length=10), nullable=False),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("short_bio", sa.Text(), nullable=True),
        sa.Column(
            "license_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'public_clip'"),
        ),
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
            "license_status IN ('public_clip', 'authorized', 'partnership')",
            name="chk_pp_license",
        ),
        sa.CheckConstraint(
            "handedness IN ('right', 'left')",
            name="chk_pp_handedness",
        ),
    )
    op.create_index("idx_pp_active_sort", "pro_players", ["is_active", "sort_order"])

    # ---------- pro_swing_clips ----------
    op.create_table(
        "pro_swing_clips",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "pro_player_id",
            sa.String(length=32),
            sa.ForeignKey("pro_players.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("club_type", sa.String(length=20), nullable=False),
        sa.Column("camera_angle", sa.String(length=20), nullable=False),
        sa.Column("video_url", sa.String(length=512), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=512), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("fps", sa.Integer(), nullable=True),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column(
            "engine_version",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'v1'"),
        ),
        sa.Column(
            "features_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("phase_timestamps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("license_status", sa.String(length=20), nullable=False),
        sa.Column("source_credit", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("captured_year", sa.SmallInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
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
            "camera_angle IN ('face_on', 'down_the_line')",
            name="chk_psc_camera",
        ),
        sa.CheckConstraint(
            "license_status IN ('public_clip', 'authorized', 'partnership')",
            name="chk_psc_license",
        ),
    )
    op.create_index(
        "idx_psc_player", "pro_swing_clips", ["pro_player_id", "club_type"]
    )
    op.create_index(
        "idx_psc_published",
        "pro_swing_clips",
        ["is_published", "club_type"],
        postgresql_where=sa.text("is_published = TRUE"),
    )

    # ---------- pro_clip_annotations ----------
    op.create_table(
        "pro_clip_annotations",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "clip_id",
            sa.String(length=32),
            sa.ForeignKey("pro_swing_clips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("annotation_type", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("time_marker_ms", sa.Integer(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
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
            "annotation_type IN ('text', 'voice', 'sketch')",
            name="chk_pca_type",
        ),
    )
    op.create_index(
        "idx_pca_clip", "pro_clip_annotations", ["clip_id", "time_marker_ms"]
    )

    # ---------- pro_topics ----------
    op.create_table(
        "pro_topics",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("code", sa.String(length=40), nullable=False, unique=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("subtitle", sa.String(length=200), nullable=True),
        sa.Column("banner_url", sa.String(length=512), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "clip_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("week_starts_at", sa.Date(), nullable=True),
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("idx_pt_published", "pro_topics", ["is_published", "week_starts_at"])

    # ---------- user_pro_favorites ----------
    op.create_table(
        "user_pro_favorites",
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "clip_id",
            sa.String(length=32),
            sa.ForeignKey("pro_swing_clips.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("idx_upf_user", "user_pro_favorites", ["user_id", "created_at"])

    # ---------- user_pro_match_history ----------
    op.create_table(
        "user_pro_match_history",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "analysis_id",
            sa.String(length=32),
            sa.ForeignKey("swing_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "matched_clip_id",
            sa.String(length=32),
            sa.ForeignKey("pro_swing_clips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("match_score", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "match_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "idx_upmh_user", "user_pro_match_history", ["user_id", "created_at"]
    )
    op.create_index("idx_upmh_analysis", "user_pro_match_history", ["analysis_id"])


def downgrade() -> None:
    op.drop_index("idx_upmh_analysis", table_name="user_pro_match_history")
    op.drop_index("idx_upmh_user", table_name="user_pro_match_history")
    op.drop_table("user_pro_match_history")
    op.drop_index("idx_upf_user", table_name="user_pro_favorites")
    op.drop_table("user_pro_favorites")
    op.drop_index("idx_pt_published", table_name="pro_topics")
    op.drop_table("pro_topics")
    op.drop_index("idx_pca_clip", table_name="pro_clip_annotations")
    op.drop_table("pro_clip_annotations")
    op.drop_index("idx_psc_published", table_name="pro_swing_clips")
    op.drop_index("idx_psc_player", table_name="pro_swing_clips")
    op.drop_table("pro_swing_clips")
    op.drop_index("idx_pp_active_sort", table_name="pro_players")
    op.drop_table("pro_players")
