"""W8-T5: events (埋点 / 错误上报通用表)

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-22

通用埋点表。前端 `track.ts` 批量 flush 过来的事件统一落这里。
与 share_actions（业务专表）并存：share_* 事件在两张表各写一条，
看板侧按 events 表做聚合即可。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("client_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "idx_events_name_created_at", "events", ["name", "created_at"]
    )
    op.create_index(
        "idx_events_user_created_at", "events", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_events_user_created_at", table_name="events")
    op.drop_index("idx_events_name_created_at", table_name="events")
    op.drop_table("events")
