"""POST /v1/feedback 集成测试（docs/02 §2.6）.

覆盖点
------
1. 携带 Token 正常提交 → 落库 + 返回 feedback_id
2. 内容空白 → 400
3. 内容 > 500 字 → 422（Pydantic 长度校验）
4. 无 Token → 401
5. 60 秒内同用户连续提交 → 第二次 429
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.feedback import Feedback


@pytest.mark.asyncio
async def test_submit_feedback_ok(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.post(
        "/v1/feedback",
        headers=auth_headers,
        json={"content": "希望加一个夜间模式", "contact": "wechat:lingniao"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["message"] == "感谢你的反馈"
    fb_id = body["data"]["feedback_id"]
    assert fb_id.startswith("fb_")

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(Feedback).where(Feedback.id == fb_id))
        ).scalar_one()
        assert row.content == "希望加一个夜间模式"
        assert row.contact == "wechat:lingniao"


@pytest.mark.asyncio
async def test_submit_feedback_blank_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.post(
        "/v1/feedback",
        headers=auth_headers,
        json={"content": "   "},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_submit_feedback_too_long_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.post(
        "/v1/feedback",
        headers=auth_headers,
        json={"content": "x" * 501},
    )
    # Pydantic FieldInfo max_length 触发 422
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_submit_feedback_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/v1/feedback", json={"content": "hi"})
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_submit_feedback_rate_limited(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    first = await client.post(
        "/v1/feedback",
        headers=auth_headers,
        json={"content": "首次反馈"},
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        "/v1/feedback",
        headers=auth_headers,
        json={"content": "60 秒内再发一次"},
    )
    assert second.status_code == 429, second.text
    assert second.json()["code"] == 42901
