"""约球 API 测试共用：mock 实名 + 同意协议."""

from __future__ import annotations

from httpx import AsyncClient


async def prepare_meetup_access(client: AsyncClient, headers: dict[str, str]) -> None:
    stamp = await client.post("/v1/meetups/safety/mock-identity", headers=headers)
    assert stamp.status_code == 200, stamp.text
    accept = await client.post("/v1/meetups/safety/accept-tos", headers=headers)
    assert accept.status_code == 200, accept.text
