"""认证相关接口的集成测试（M1-T1, W8-T4）."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.config import settings


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


# ==================== W8-T4：真实模式错误码映射 ====================
class _FakeWechatHTTPResponse:
    """轻量假 httpx.Response，只提供 raise_for_status / json()."""

    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}",
                request=httpx.Request("GET", "https://api.weixin.qq.com"),
                response=self,  # type: ignore[arg-type]
            )

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    """假 httpx.AsyncClient：把 .get(url, params) 固定返回构造时给的 payload."""

    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self._status_code = status_code

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str, params: dict[str, Any] | None = None) -> _FakeWechatHTTPResponse:
        return _FakeWechatHTTPResponse(self._payload, self._status_code)


@pytest.fixture
def real_wechat_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """关掉 mock，强制 code2session 走真实 httpx 分支。"""
    monkeypatch.setattr(settings, "WECHAT_MOCK_LOGIN", False)


@pytest.mark.asyncio
async def test_wechat_login_invalid_code_returns_401(
    client: AsyncClient,
    real_wechat_mode: None,
    monkeypatch: pytest.MonkeyPatch,
):
    """W8-T4：真实模式下，微信返回 errcode=40029（code 失效）应映射为 401 / 业务码 40104。

    用例覆盖前端的"重新 wx.login 重试"分支：401 时客户端清掉本地 token + 重新拉 code。
    """
    fake_payload = {"errcode": 40029, "errmsg": "invalid code"}
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: _FakeAsyncClient(fake_payload),
    )

    resp = await client.post("/v1/auth/wechat-login", json={"code": "expired_code"})
    assert resp.status_code == 401, resp.text
    body = resp.json()
    assert body["code"] == 40104
    assert "失效" in body["message"]


@pytest.mark.asyncio
async def test_wechat_login_third_party_error_returns_502(
    client: AsyncClient,
    real_wechat_mode: None,
    monkeypatch: pytest.MonkeyPatch,
):
    """W8-T4：微信返回非用户原因错误（如 appid/secret 错配 errcode=40013）应映射为 502 / 50201。

    这类应该让运维去查配置，不是让用户重试。
    """
    fake_payload = {"errcode": 40013, "errmsg": "invalid appid"}
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: _FakeAsyncClient(fake_payload),
    )

    resp = await client.post("/v1/auth/wechat-login", json={"code": "any_code"})
    assert resp.status_code == 502, resp.text
    body = resp.json()
    assert body["code"] == 50201


@pytest.mark.asyncio
async def test_wechat_login_network_error_returns_502(
    client: AsyncClient,
    real_wechat_mode: None,
    monkeypatch: pytest.MonkeyPatch,
):
    """W8-T4：网络异常（DNS/超时/TLS）也应映射为 502，提示"微信服务异常"。"""

    class _BoomClient(_FakeAsyncClient):
        async def get(self, url: str, params: dict[str, Any] | None = None) -> _FakeWechatHTTPResponse:
            raise httpx.ConnectTimeout("simulated network timeout")

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: _BoomClient({}, 200),
    )

    resp = await client.post("/v1/auth/wechat-login", json={"code": "any_code"})
    assert resp.status_code == 502, resp.text
    assert resp.json()["code"] == 50201


@pytest.mark.asyncio
async def test_wechat_open_login_merges_mini_program_user(
    client: AsyncClient, fresh_code: str
):
    """MOCK 下同 code 的小程序与开放平台登录应共享 unionid，从而合并为同一用户."""
    r1 = await client.post("/v1/auth/wechat-login", json={"code": fresh_code})
    assert r1.status_code == 200, r1.text
    uid = r1.json()["data"]["user"]["id"]

    r2 = await client.post("/v1/auth/wechat-open-login", json={"code": fresh_code})
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["data"]["user"]["id"] == uid
    assert body2["data"]["is_new_user"] is False


@pytest.mark.asyncio
async def test_wechat_login_merges_after_open_app(
    client: AsyncClient, fresh_code: str
):
    """先发起来自 App 的 mock 登录，再同 code 走小程序登录亦应合并."""
    r1 = await client.post("/v1/auth/wechat-open-login", json={"code": fresh_code})
    assert r1.status_code == 200, r1.text
    uid = r1.json()["data"]["user"]["id"]
    assert r1.json()["data"]["is_new_user"] is True

    r2 = await client.post("/v1/auth/wechat-login", json={"code": fresh_code})
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["data"]["user"]["id"] == uid
    assert body2["data"]["is_new_user"] is False


@pytest.mark.asyncio
async def test_wechat_open_login_invalid_code_returns_401(
    client: AsyncClient,
    real_wechat_mode: None,
    monkeypatch: pytest.MonkeyPatch,
):
    fake_payload = {"errcode": 40029, "errmsg": "invalid code"}
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **_: _FakeAsyncClient(fake_payload),
    )

    resp = await client.post("/v1/auth/wechat-open-login", json={"code": "bad"})
    assert resp.status_code == 401, resp.text
    assert resp.json()["code"] == 40104


@pytest.mark.asyncio
async def test_apple_login_mock_creates_user(client: AsyncClient, fresh_code: str):
    """APPLE_MOCK_LOGIN 下 mock- token 应创建用户并返回 JWT."""
    if not settings.APPLE_MOCK_LOGIN:
        pytest.skip("APPLE_MOCK_LOGIN disabled")
    token = f"mock-apple-{fresh_code}"
    resp = await client.post(
        "/v1/auth/apple-login",
        json={"identity_token": token, "full_name": "Apple球友"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["is_new_user"] is True
    assert data["token"]
    assert data["user"]["nickname"] == "Apple球友"

    again = await client.post(
        "/v1/auth/apple-login",
        json={"identity_token": token},
    )
    assert again.status_code == 200, again.text
    assert again.json()["data"]["user"]["id"] == data["user"]["id"]
    assert again.json()["data"]["is_new_user"] is False
