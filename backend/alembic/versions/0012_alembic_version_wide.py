"""加长 alembic_version.version_num，避免长 revision id 无法再写入."""

from typing import Sequence, Union

from alembic import op

revision: str = "0012_ver_num_w128"
down_revision: Union[str, None] = "0011_list_alive_ix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"
    )


def downgrade() -> None:
    # 缩回 VARCHAR(32) 易因较长 revision id 失败，不再自动执行。
    pass
