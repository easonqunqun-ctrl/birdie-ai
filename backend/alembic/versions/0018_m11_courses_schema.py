"""M11 P2-M11-01 课程体系 4 张表.

逻辑编号：docs/03 §8.7 规划 0010；实际落库编号：0018（按 alembic head 续编：
head=0016_feedback，M9-01 占 0017_m9_user_profiles_v2 → 0018）。

revision: 0018_m11_courses_schema
down_revision: 0017_m9_user_profiles_v2
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_m11_courses_schema"
down_revision: Union[str, None] = "0017_m9_user_profiles_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("code", sa.String(length=40), nullable=False, unique=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("subtitle", sa.String(length=200), nullable=True),
        sa.Column("cover_url", sa.String(length=512), nullable=True),
        sa.Column("stage", sa.SmallInteger(), nullable=False),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_member_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "learning_objectives",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "estimated_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
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
        sa.CheckConstraint("stage BETWEEN 1 AND 7", name="chk_courses_stage"),
    )
    op.create_index(
        "idx_courses_stage",
        "courses",
        ["stage", "sort_order"],
        postgresql_where=sa.text("is_published = TRUE"),
    )
    op.create_index("idx_courses_member", "courses", ["is_member_only", "stage"])

    op.create_table(
        "lessons",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "course_id",
            sa.String(length=32),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=40), nullable=False, unique=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "duration_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("15"),
        ),
        sa.Column("video_url", sa.String(length=512), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column(
            "drill_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "pro_clip_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("quiz_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "pass_criteria",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("course_id", "sort_order", name="uq_lessons_course_sort"),
    )
    op.create_index("idx_lessons_course_id", "lessons", ["course_id", "sort_order"])

    op.create_table(
        "user_course_progress",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lesson_id",
            sa.String(length=32),
            sa.ForeignKey("lessons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'not_started'"),
        ),
        sa.Column("last_score", sa.Integer(), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("passed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "failed_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_ucp_user_lesson"),
        sa.CheckConstraint(
            "status IN ('not_started', 'in_progress', 'passed', 'failed')",
            name="chk_ucp_status",
        ),
    )
    op.create_index(
        "idx_ucp_user_passed",
        "user_course_progress",
        ["user_id", "status"],
        postgresql_where=sa.text("status = 'passed'"),
    )

    op.create_table(
        "course_certificates",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.String(length=32),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.SmallInteger(), nullable=False),
        sa.Column("cert_url", sa.String(length=512), nullable=True),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint("stage BETWEEN 1 AND 7", name="chk_cc_stage"),
    )
    op.create_index(
        "uq_cc_user_course",
        "course_certificates",
        ["user_id", "course_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "idx_cc_user_issued",
        "course_certificates",
        ["user_id", "issued_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_cc_user_issued", table_name="course_certificates")
    op.drop_index("uq_cc_user_course", table_name="course_certificates")
    op.drop_table("course_certificates")
    op.drop_index("idx_ucp_user_passed", table_name="user_course_progress")
    op.drop_table("user_course_progress")
    op.drop_index("idx_lessons_course_id", table_name="lessons")
    op.drop_table("lessons")
    op.drop_index("idx_courses_member", table_name="courses")
    op.drop_index("idx_courses_stage", table_name="courses")
    op.drop_table("courses")
