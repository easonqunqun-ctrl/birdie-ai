"""用户相关接口的集成测试（M1-T1）。

覆盖：
- GET /v1/users/me：返回用户信息、stats、真实 quota。
- PATCH /v1/users/me：更新昵称、头像。
- POST /v1/users/me/onboarding：完成引导，写入档案。
- 鉴权：无 Token / 错 Token 都应 401。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_me_requires_auth(client: AsyncClient):
    """/users/me 无 Token 应 401。"""
    resp = await client.get("/v1/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_rejects_invalid_token(client: AsyncClient):
    """/users/me 伪造 Token 应 401。"""
    resp = await client.get(
        "/v1/users/me",
        headers={"Authorization": "Bearer invalid.token.xxx"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_returns_stats_and_quota(client: AsyncClient, auth_headers: dict[str, str]):
    """/users/me 应返回 stats（全 0）与免费用户的默认配额。"""
    resp = await client.get("/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    assert data["membership_type"] == "free"
    assert data["onboarding_completed"] is False

    stats = data["stats"]
    assert stats == {
        "total_analyses": 0,
        "total_practices": 0,
        "streak_days": 0,
        "best_score": 0,
        "score_improvement": 0,
    }

    quota = data["quota"]
    # 免费用户默认：本月 3 次分析 / 每日 5 轮对话。
    assert quota["analysis_total"] == 3
    assert quota["analysis_remaining"] == 3
    assert quota["chat_total_today"] == 5
    assert quota["chat_remaining_today"] == 5


@pytest.mark.asyncio
async def test_patch_me_updates_nickname_and_avatar(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """PATCH /users/me 应能更新昵称与头像，且只更新传入的字段。"""
    resp = await client.patch(
        "/v1/users/me",
        headers=auth_headers,
        json={"nickname": "测试球友", "avatar_url": "https://cdn.example.com/a.png"},
    )
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    assert data["nickname"] == "测试球友"
    assert data["avatar_url"] == "https://cdn.example.com/a.png"

    # 再发一次只更新昵称，头像不应被清空。
    resp2 = await client.patch(
        "/v1/users/me",
        headers=auth_headers,
        json={"nickname": "球友二号"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()["data"]
    assert data2["nickname"] == "球友二号"
    assert data2["avatar_url"] == "https://cdn.example.com/a.png"


@pytest.mark.asyncio
async def test_patch_me_rejects_too_short_nickname(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """昵称长度约束（2-12）应由 Pydantic 拦截。"""
    resp = await client.patch(
        "/v1/users/me",
        headers=auth_headers,
        json={"nickname": "a"},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_onboarding_writes_profile_and_marks_completed(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """完成引导后 onboarding_completed=True，档案字段按入参保存。"""
    payload = {
        "golf_level": "intermediate",
        "primary_goals": ["distance", "accuracy"],
        "weekly_practice_frequency": "frequent",
    }
    resp = await client.post("/v1/users/me/onboarding", headers=auth_headers, json=payload)
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    assert data["onboarding_completed"] is True
    assert data["golf_level"] == "intermediate"
    assert data["primary_goals"] == ["distance", "accuracy"]
    assert data["weekly_practice_frequency"] == "frequent"

    # 再 GET 一次确认落库。
    me = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me["onboarding_completed"] is True
    assert me["golf_level"] == "intermediate"


@pytest.mark.asyncio
async def test_patch_me_can_set_onboarding_completed_true(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """PATCH /me 支持把 onboarding_completed 置为 true（引导"跳过"入口）。"""
    resp = await client.patch(
        "/v1/users/me",
        headers=auth_headers,
        json={"onboarding_completed": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["onboarding_completed"] is True


@pytest.mark.asyncio
async def test_patch_me_rejects_setting_onboarding_completed_false(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """PATCH /me 不允许把 onboarding_completed 置为 false。"""
    resp = await client.patch(
        "/v1/users/me",
        headers=auth_headers,
        json={"onboarding_completed": False},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 40010


@pytest.mark.asyncio
async def test_onboarding_rejects_empty_goals(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """primary_goals 至少 1 个（schema min_length=1）。"""
    resp = await client.post(
        "/v1/users/me/onboarding",
        headers=auth_headers,
        json={
            "golf_level": "beginner",
            "primary_goals": [],
            "weekly_practice_frequency": "once",
        },
    )
    assert resp.status_code in (400, 422)
