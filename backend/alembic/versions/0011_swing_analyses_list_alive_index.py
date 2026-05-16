"""列表/曲线常用筛选：用户历史仅查未删且非示例 — 部分索引"""

from typing import Sequence, Union

from alembic import op

# 须 ≤32 字符：`alembic_version.version_num` 默认为 VARCHAR(32)，过长revision会写库失败。
revision: str = "0011_list_alive_ix"
down_revision: Union[str, None] = "0010_swing_analysis_deleted_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_swing_analyses_list_alive
        ON swing_analyses (user_id, created_at DESC)
        WHERE deleted_at IS NULL AND is_sample IS FALSE;
        """
    )


def downgrade() -> None:
    op.drop_index("idx_swing_analyses_list_alive", table_name="swing_analyses")
