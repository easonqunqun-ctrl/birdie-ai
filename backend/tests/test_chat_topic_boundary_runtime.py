"""P-02 运行时：话题边界 pre-check（不扣配额、不调 LLM）."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_off_topic_message_returns_refusal_without_consuming_quota(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    session = (
        await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    ).json()["data"]["session_id"]

    me_before = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    remaining_before = me_before["quota"]["chat_remaining_today"]

    resp = await client.post(
        f"/v1/chat/sessions/{session}/messages",
        headers={**auth_headers, "Accept": "application/json"},
        json={"content": "比特币还能涨吗"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert "专长" in body["assistant_message"]["content"]
    assert body["quota_remaining"] == remaining_before

    me_after = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me_after["quota"]["chat_remaining_today"] == remaining_before


@pytest.mark.asyncio
async def test_medical_message_returns_medical_guidance(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    session = (
        await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    ).json()["data"]["session_id"]
    resp = await client.post(
        f"/v1/chat/sessions/{session}/messages",
        headers={**auth_headers, "Accept": "application/json"},
        json={"content": "挥杆后肩膀疼要不要去看医生"},
    )
    assert resp.status_code == 200
    assert "医生" in resp.json()["data"]["assistant_message"]["content"]


@pytest.mark.asyncio
async def test_gambling_message_returns_gambling_refusal(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    session = (
        await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    ).json()["data"]["session_id"]
    resp = await client.post(
        f"/v1/chat/sessions/{session}/messages",
        headers={**auth_headers, "Accept": "application/json"},
        json={"content": "下场打球怎么下注"},
    )
    assert resp.status_code == 200
    assert "赌球" in resp.json()["data"]["assistant_message"]["content"]


@pytest.mark.asyncio
async def test_golf_message_still_consumes_quota(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    session = (
        await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    ).json()["data"]["session_id"]
    me_before = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    remaining_before = me_before["quota"]["chat_remaining_today"]

    resp = await client.post(
        f"/v1/chat/sessions/{session}/messages",
        headers={**auth_headers, "Accept": "application/json"},
        json={"content": "我的右曲球怎么纠正"},
    )
    assert resp.status_code == 200

    me_after = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me_after["quota"]["chat_remaining_today"] == remaining_before - 1
