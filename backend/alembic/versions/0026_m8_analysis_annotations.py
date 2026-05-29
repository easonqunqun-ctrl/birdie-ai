"""M8-04 / M12-09 · analysis_annotations 表（教练 video_ref 批注 MVP）."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_m8_analysis_annotations"
down_revision: Union[str, None] = "0025_swing_analyses_engine_warnings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_annotations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("coach_user_id", sa.String(length=32), nullable=False),
        sa.Column("student_user_id", sa.String(length=32), nullable=False),
        sa.Column("analysis_id", sa.String(length=32), nullable=False),
        sa.Column("annotation_type", sa.String(length=20), nullable=False),
        sa.Column("pro_clip_id", sa.String(length=32), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column(
            "audit_status",
            sa.String(length=20),
            nullable=False,
            server_default="approved",
        ),
        sa.Column(
            "is_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        sa.ForeignKeyConstraint(["analysis_id"], ["swing_analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["coach_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pro_clip_id"], ["pro_swing_clips.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "annotation_type IN ('voice','text','sketch','video_ref')",
            name="chk_ann_type",
        ),
        sa.CheckConstraint(
            "audit_status IN ('pending','approved','rejected','manual_review')",
            name="chk_ann_audit_status",
        ),
    )
    op.create_index(
        "idx_ann_analysis_visible",
        "analysis_annotations",
        ["analysis_id", "is_visible"],
    )
    op.create_index(
        "idx_ann_coach",
        "analysis_annotations",
        ["coach_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_ann_coach", table_name="analysis_annotations")
    op.drop_index("idx_ann_analysis_visible", table_name="analysis_annotations")
    op.drop_table("analysis_annotations")
