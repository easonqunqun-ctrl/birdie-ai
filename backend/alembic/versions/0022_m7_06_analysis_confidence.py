"""P2-M7-06：swing_analyses + analysis_issues 增 confidence 列。

详 docs/release-notes/p2-m7-06-confidence-pipeline-kickoff.md §4.2。

新增列
------
- swing_analyses.analysis_confidence FLOAT NOT NULL DEFAULT 1.0
  V1 引擎遗留报告兜底 1.0；客户端 <0.5 触发「建议重拍」CTA
- swing_analyses.feature_confidences JSONB NULL
  每特征 confidence (feature_name → 0-1)
- analysis_issues.confidence FLOAT NULL
- analysis_issues.confidence_tier VARCHAR(20) NULL

依赖链（按 PR 合入顺序）：
0016_feedback → 0017_m9_user_profiles_v2 (PR #90)
              → 0018_m11_courses_schema (PR #91)
              → 0019_m12_pro_library_schema (PR #92)
              → 0020_m13_meetup_schema (PR #93)
              → 0021_swing_analyses_engine_version (PR #94)
              → 0022_m7_06_analysis_confidence (本 PR)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_m7_06_analysis_confidence"
down_revision: Union[str, None] = "0021_swing_analyses_engine_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "swing_analyses",
        sa.Column(
            "analysis_confidence",
            sa.Float(),
            nullable=False,
            server_default="1.0",
        ),
    )
    op.add_column(
        "swing_analyses",
        sa.Column(
            "feature_confidences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_swing_analyses_confidence",
        "swing_analyses",
        ["analysis_confidence"],
    )

    op.add_column(
        "analysis_issues",
        sa.Column("confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "analysis_issues",
        sa.Column("confidence_tier", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_issues", "confidence_tier")
    op.drop_column("analysis_issues", "confidence")
    op.drop_index("idx_swing_analyses_confidence", table_name="swing_analyses")
    op.drop_column("swing_analyses", "feature_confidences")
    op.drop_column("swing_analyses", "analysis_confidence")
