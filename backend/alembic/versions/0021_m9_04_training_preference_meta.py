"""M9-04 训练偏好结构化：training_preference_meta JSONB.

Revision ID: 0021_m9_04_training_preference_meta
Revises: 0020_m13_party_play
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

回滚
----
``downgrade`` 仅 DROP COLUMN，对历史读写无影响（M9-04 prompt 注入会读不到
该列 → 自动退回 M9-01 style 单字段路径）。
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_m9_04_training_preference_meta"
# 暂以 M9-01 (0017) 为父；若 M11/M12/M13 (0018/0019/0020) 先合并，
# 本 PR rebase 时把 down_revision 调成最后一条 0020_xxx 即可（纯线性追加）。
down_revision: Union[str, None] = "0017_m9_user_profiles_v2"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


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
