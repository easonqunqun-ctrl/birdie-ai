"""微信小程序消息推送 /v1/wechat/mp-push 单测."""

from __future__ import annotations

import hashlib
import json

import pytest
from httpx import AsyncClient

from app.config import settings


def _mp_push_signature(token: str, timestamp: str, nonce: str) -> str:
    arr = sorted([token, timestamp, nonce])
    return hashlib.sha1("".join(arr).encode()).hexdigest()


@pytest.mark.asyncio
async def test_mp_push_verify_returns_echostr_when_signature_ok(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "WECHAT_MP_PUSH_TOKEN", "push_token_test")
    ts = "1710000000"
    nonce = "nonce123"
    sig = _mp_push_signature("push_token_test", ts, nonce)
    resp = await client.get(
        "/v1/wechat/mp-push",
        params={
            "signature": sig,
            "timestamp": ts,
            "nonce": nonce,
            "echostr": "hello_wechat",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "hello_wechat"


@pytest.mark.asyncio
async def test_mp_push_verify_rejects_bad_signature(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "WECHAT_MP_PUSH_TOKEN", "push_token_test")
    resp = await client.get(
        "/v1/wechat/mp-push",
        params={
            "signature": "bad",
            "timestamp": "1",
            "nonce": "2",
            "echostr": "x",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_mp_push_unknown_event_returns_success(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "WECHAT_MP_PUSH_TOKEN", "push_token_test")
    resp = await client.post(
        "/v1/wechat/mp-push",
        content=json.dumps({"Event": "subscribe"}),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ErrCode"] == 0
    assert body["ErrMsg"] == "ignored"


@pytest.mark.asyncio
async def test_mp_push_post_rejects_bad_signature(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "WECHAT_MP_PUSH_TOKEN", "push_token_test")
    resp = await client.post(
        "/v1/wechat/mp-push",
        params={"signature": "bad", "timestamp": "1", "nonce": "2"},
        content='{"Event":"subscribe"}',
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 403
