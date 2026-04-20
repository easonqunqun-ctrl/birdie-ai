"""chat_sessions add system_prompt_version

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-20

M3-T2 需要把"某次会话用的是哪版 system prompt"记下来，后续 prompt 迭代时：
- 用户如果在半途升级了 prompt 模板，后端应**只给新消息用新模板**，旧消息的
  assistant 回复不会被追溯解释成"在新模板里理解"；
- 数据分析侧想 A/B 对比 prompt v1 vs v2 的满意度，也依赖这个字段。

字段设计：
- VARCHAR(16)，够容纳 "v1"/"v1.1"/"v2-beta" 这类语义化版本号
- nullable=True：历史 T1 数据没有这个字段，迁移时自动置空；代码侧读取时回退到 "v0"
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("system_prompt_version", sa.String(16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "system_prompt_version")
