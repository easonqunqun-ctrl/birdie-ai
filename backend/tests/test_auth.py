"""认证相关接口的集成测试（M1-T1）."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_wechat_login_creates_new_user(client: AsyncClient, fresh_code: str):
    """首次登录应创建新用户，返回 is_new_user=True。"""
    resp = await client.post("/v1/auth/wechat-login", json={"code": fresh_code})
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["code"] == 0

    data = body["data"]
    assert data["is_new_user"] is True
    assert data["token"]
    assert data["expires_in"] > 0

    user = data["user"]
    assert user["id"].startswith("usr_")
    assert user["membership_type"] == "free"
    assert user["onboarding_completed"] is False
    # 登录接口不主动填 quota/stats（走 /users/me 拿）
    assert user["quota"] is None
    assert user["stats"] is None


@pytest.mark.asyncio
async def test_wechat_login_is_idempotent_for_same_code(client: AsyncClient, fresh_code: str):
    """同一 code 再次登录应返回同一用户且 is_new_user=False。"""
    first = (await client.post("/v1/auth/wechat-login", json={"code": fresh_code})).json()["data"]
    second = (await client.post("/v1/auth/wechat-login", json={"code": fresh_code})).json()["data"]

    assert first["user"]["id"] == second["user"]["id"]
    assert first["is_new_user"] is True
    assert second["is_new_user"] is False


@pytest.mark.asyncio
async def test_refresh_token_returns_new_token(client: AsyncClient, auth_headers: dict[str, str]):
    """携带有效 Token 调用 refresh-token 应得到新 Token。"""
    resp = await client.post("/v1/auth/refresh-token", headers=auth_headers)
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    assert data["token"]
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_refresh_token_rejects_missing_bearer(client: AsyncClient):
    """无 Token 调用 refresh-token 应 401。"""
    resp = await client.post("/v1/auth/refresh-token")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rejects_bad_bearer(client: AsyncClient):
    """错误 Token 调用 refresh-token 应 401。"""
    resp = await client.post(
        "/v1/auth/refresh-token",
        headers={"Authorization": "Bearer not.a.real.jwt"},
    )
    assert resp.status_code == 401
