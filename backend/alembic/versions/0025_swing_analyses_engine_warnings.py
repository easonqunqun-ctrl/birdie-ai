"""P2-W10：swing_analyses 增 engine_warnings JSONB 列（W8/W9 引擎产物透传客户端）.

详 docs/release-notes/p2-phase2-sprint-plan.md W10。

新增列
------
- swing_analyses.engine_warnings JSONB NULL
  W8 落地的 engine_warnings（decoded_hevc / hdr_tonemapped / slowmo_detected /
  fps_upsampled / audio_kept / fallback_to_v1 等），从 ai_engine AnalyzeResult
  原样透传落库；客户端报告页"调试浮层"展示。
  V1 引擎 + 老报告：NULL（视为「无附加诊断信息」）。

依赖链：
0024_m13_02_venues_geo → 0025_swing_analyses_engine_warnings (本 PR)

为什么不重用 quality_warnings
-----------------------------
quality_warnings 是早期约定的「人类可读的非阻断质量提示」（low_light / camera_shake）
仅 ai_engine 当下生成；engine_warnings 是 W8 新增的「机器结构化诊断 + ts」格式，含
``code/level/detail/ts`` 四字段，与 quality_warnings 不可互换。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_swing_analyses_engine_warnings"
down_revision: Union[str, None] = "0024_m13_02_venues_geo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "swing_analyses",
        sa.Column(
            "engine_warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("swing_analyses", "engine_warnings")
