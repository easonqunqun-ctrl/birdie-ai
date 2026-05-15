"""埋点 / 错误上报事件模型（W8-T5）。

表结构
------
- `id`        str(32) PK：evt_<nanoid>
- `user_id`   str(32) nullable FK → users.id
              未登录场景（如 App.onError 在首启前触发）允许为空
- `name`      str(64)：事件名，白名单见 `app.services.event_service.EVENT_NAMES`；
              允许任意非空字符串，服务层做白名单校验后再决定是否落库
- `payload`   JSONB，事件载荷（context / 错误栈 / 页面参数 等）；可 NULL
- `client_ts` DateTime(tz)：客户端打点时刻；用于时钟漂移监控
- `created_at` DateTime(tz)：服务端落库时刻；用于查询和索引

索引
----
- `idx_events_name_created_at`：日活 / 事件计数 SQL 按 name 过滤
- `idx_events_user_created_at` ：用户行为路径回放按 user + 时间过滤

与 `share_actions` 的关系
-------------------------
`share_actions` 是 W7 阶段为分享埋点单独建的业务表，有 `bonus_*` 字段。
本表（events）是通用泛化埋点的落地点：share 相关事件也会复制一条到
events（name=`share_report`），因为运营看板更愿意拉一张通用表。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    client_ts: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_events_name_created_at", "name", "created_at"),
        Index("idx_events_user_created_at", "user_id", "created_at"),
    )
