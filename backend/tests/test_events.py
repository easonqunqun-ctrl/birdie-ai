"""W8-T5：/v1/events 批量埋点集成测试。

覆盖点
------
1. 带 Token 的批量上报 → accepted=N, rejected=0
2. 匿名（无 Authorization）也能上报 → 同样落库
3. 非白名单事件名 → rejected+1，白名单事件照常 accepted
4. 单批 > 50 条时多余的部分被 rejected
5. 超大 payload 被裁断（校验落库对象）
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.event import Event


@pytest.mark.asyncio
async def test_events_accept_core_batch(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    payload = {
        "events": [
            {"name": "page_view", "payload": {"path": "/pages/index/index"}},
            {"name": "analysis_submit", "payload": {"analysis_id": "a1"}},
            {"name": "analysis_done", "payload": {"analysis_id": "a1"}},
            {"name": "share_report", "payload": {"target_id": "a1"}},
            {"name": "pay_success", "payload": {"order_id": "o1", "mode": "mock"}},
            {"name": "error_report", "payload": {"message": "boom"}},
        ]
    }
    resp = await client.post("/v1/events", headers=auth_headers, json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["accepted"] == 6
    assert body["data"]["rejected"] == 0

    # 验证事件确实落库
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Event).where(Event.name == "analysis_submit")
        )
        rows = result.scalars().all()
        assert any(r.payload and r.payload.get("analysis_id") == "a1" for r in rows)


@pytest.mark.asyncio
async def test_events_allow_anonymous(client: AsyncClient) -> None:
    # 不带 Authorization 也能成功上报（覆盖首启前 App.onError 场景）
    resp = await client.post(
        "/v1/events",
        json={"events": [{"name": "error_report", "payload": {"message": "x"}}]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["accepted"] == 1


@pytest.mark.asyncio
async def test_events_reject_unknown_name(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.post(
        "/v1/events",
        headers=auth_headers,
        json={
            "events": [
                {"name": "page_view"},
                {"name": "some_random_event"},
                {"name": "another_bad"},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["accepted"] == 1
    assert body["data"]["rejected"] == 2


@pytest.mark.asyncio
async def test_events_cap_batch_size(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # 60 条 page_view，超过 MAX_BATCH_SIZE=50 的会被 rejected
    resp = await client.post(
        "/v1/events",
        headers=auth_headers,
        json={"events": [{"name": "page_view"} for _ in range(60)]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["accepted"] == 50
    assert body["data"]["rejected"] == 10


@pytest.mark.asyncio
async def test_events_truncate_large_payload(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # payload > 8KB → 入库时被裁断
    huge_text = "x" * (10 * 1024)
    resp = await client.post(
        "/v1/events",
        headers=auth_headers,
        json={
            "events": [
                {"name": "error_report", "payload": {"message": huge_text}},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["accepted"] == 1

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Event)
            .where(Event.name == "error_report")
            .order_by(Event.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one()
        assert row.payload is not None
        # 被截断的载荷会带 _truncated 标记
        assert row.payload.get("_truncated") is True
