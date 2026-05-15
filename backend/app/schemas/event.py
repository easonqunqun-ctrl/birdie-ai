"""埋点 / 错误上报 schema（W8-T5）."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TrackEvent(BaseModel):
    """单条埋点事件。"""

    name: str = Field(max_length=64, description="事件名，见 EVENT_NAMES 白名单")
    payload: dict[str, Any] | list[Any] | None = Field(
        default=None, description="自定义载荷（dict 或 list），可空"
    )
    client_ts: int | float | str | None = Field(
        default=None,
        description="客户端打点时刻，ms 时间戳或 ISO8601 字符串；用于服务端对时钟漂移",
    )


class TrackBatchRequest(BaseModel):
    """`POST /v1/events` 请求体。"""

    events: list[TrackEvent] = Field(
        default_factory=list, description="事件批次，单批 ≤ 50"
    )


class TrackBatchResponse(BaseModel):
    accepted: int
    rejected: int = Field(description="因名字不在白名单、超批量上限等原因被丢弃的条数")
