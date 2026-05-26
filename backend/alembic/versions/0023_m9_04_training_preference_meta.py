"""M9-04 训练偏好结构化：training_preference_meta JSONB.

Revision ID: 0023_m9_04_training_preference_meta
Revises: 0022_m7_06_analysis_confidence
Create Date: 2026-05-26

设计动机
--------
M9-01 已有 ``training_preference VARCHAR(20)``（style：video/text/mixed），
M9-04 需进一步表达 ``cadence`` 与 ``preferred_drill_types``。为不破坏 M9-01
schema / CHECK 约束、保持向下兼容，**追加** 独立 JSONB 列：

```
training_preference_meta = {
  "cadence": "daily" | "2x_per_week" | "weekly",
  "preferred_drill_types": ["rhythm", "swing_plane", ...]
}
```

style 字段仍走 M9-01 ``training_preference`` VARCHAR；客户端读时合并视图。

依赖链（按 PR 合入顺序）：
0016_feedback → 0017_m9_user_profiles_v2 (PR #90)
              → 0018_m11_courses_schema (PR #91)
              → 0019_m12_pro_library_schema (PR #92)
              → 0020_m13_meetup_schema (PR #93)
              → 0021_swing_analyses_engine_version (PR #94)
              → 0022_m7_06_analysis_confidence (PR #97)
              → 0023_m9_04_training_preference_meta (本 PR #104)

回滚
----
``downgrade`` 仅 DROP COLUMN，对历史读写无影响（M9-04 prompt 注入会读不到
该列 → 自动退回 M9-01 style 单字段路径）。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0023_m9_04_training_preference_meta"
# Rebase 后：链入 0022_m7_06_analysis_confidence 之后（单线性，无 alembic 多头）。
down_revision: str | None = "0022_m7_06_analysis_confidence"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profiles_v2",
        sa.Column(
            "training_preference_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profiles_v2", "training_preference_meta")
