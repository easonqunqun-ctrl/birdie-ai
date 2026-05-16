"""PR4 · 并行工程 backlog：补充冒烟用例（分析列表分页、chat 会话列表需登录、下单契约）."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.analysis import SwingAnalysis


async def _register(client: AsyncClient) -> tuple[str, dict[str, str]]:
    r = await client.post("/v1/auth/wechat-login", json={"code": f"pblr_{uuid4().hex}"})
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    return body["user"]["id"], {"Authorization": f"Bearer {body['token']}"}


async def _seed_completed(user_id: str) -> str:
    aid = new_id("ana")
    async with AsyncSessionLocal() as db:
        db.add(
            SwingAnalysis(
                id=aid,
                user_id=user_id,
                video_url="s3://fake/v.mp4",
                video_file_size=1024,
                camera_angle="face_on",
                club_type="driver",
                status="completed",
                is_sample=False,
                overall_score=71,
                thumbnail_url="https://cdn.example.com/thumb.jpg",
                analyzed_at=datetime.now(UTC),
            )
        )
        await db.commit()
    return aid


@pytest.mark.asyncio
async def test_analyses_list_page_size_returns_subset(client: AsyncClient) -> None:
    uid, headers = await _register(client)
    for _ in range(3):
        await _seed_completed(uid)

    r = await client.get("/v1/analyses?page=1&page_size=2", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] >= 3
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_chat_sessions_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/v1/chat/sessions")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_payment_create_order_requires_body_plan_type(client: AsyncClient) -> None:
    _, headers = await _register(client)
    bad = await client.post("/v1/payments/orders", headers=headers, json={})
    assert bad.status_code in (400, 422)

