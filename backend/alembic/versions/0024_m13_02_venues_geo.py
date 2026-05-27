"""M13-02 venues 地理坐标：latitude / longitude 列 + 联合索引.

Revision ID: 0024_m13_02_venues_geo
Revises: 0023_m9_04_training_preference_meta
Create Date: 2026-05-27

设计动机
--------
M13-02 nearby 搜索需要 venue 经纬度。M13 schema (alembic 0020) 当时只入了
``city / venue_type / status``，没纳入地理坐标——本 migration 追加：

- ``latitude`` ``Numeric(9,6)`` nullable
- ``longitude`` ``Numeric(9,6)`` nullable
- CHECK ``chk_venue_geo_range``：两列要么同时 NULL，要么落在合法范围
- 部分索引 ``idx_venues_geo``：只对 ``status='active'`` 且 ``latitude IS NOT NULL``
  建索引，减少 index bloat（大量未填坐标的 UGC venue 不进 index）

依赖链
------
0023_m9_04_training_preference_meta → 0024_m13_02_venues_geo（本 PR）

回滚
----
``downgrade`` DROP INDEX → DROP CONSTRAINT → DROP COLUMN：
- 已写入的 lat/lng 数据会一并丢失（这是 schema 回滚的代价）
- nearby 端点会返空（service 层 fallback：column missing → 0 results）
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0024_m13_02_venues_geo"
down_revision: str | None = "0023_m9_04_training_preference_meta"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "venues",
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
    )
    op.add_column(
        "venues",
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
    )
    op.create_check_constraint(
        "chk_venue_geo_range",
        "venues",
        "(latitude IS NULL AND longitude IS NULL) OR "
        "(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)",
    )
    # 部分索引（partial index）：active + 有坐标的才进 index
    op.create_index(
        "idx_venues_geo",
        "venues",
        ["latitude", "longitude"],
        postgresql_where=sa.text(
            "status = 'active' AND latitude IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("idx_venues_geo", table_name="venues")
    op.drop_constraint("chk_venue_geo_range", "venues", type_="check")
    op.drop_column("venues", "longitude")
    op.drop_column("venues", "latitude")
