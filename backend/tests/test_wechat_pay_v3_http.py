"""微信支付 V3 HTTP 层自检：网络异常与成功响应 JSON 解析（不调用真实 api.mch.weixin.qq.com）."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.integrations.wechat_pay_v3 import (
    WechatPayRequestError,
    WechatPayV3Context,
    _decode_success_json,
)


def _test_rsa_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        .decode("utf-8")
    )


@pytest.fixture
def v3_ctx() -> WechatPayV3Context:
    return WechatPayV3Context(
        mchid="1900000109",
        appid="wx_test_appid",
        apiv3_key="01234567890123456789012345678901",
        mch_serial="mock_serial_no",
        private_key_pem=_test_rsa_pem(),
        notify_url="https://example.com/payments/wechat/notify",
    )


def test_decode_success_json_ok() -> None:
    r = httpx.Response(200, json={"prepay_id": "wx_prepay_mock"})
    assert _decode_success_json(r, "/v3/pay/transactions/jsapi")["prepay_id"] == "wx_prepay_mock"


def test_decode_success_json_invalid_raises() -> None:
    r = httpx.Response(200, text="not-json")
    with pytest.raises(WechatPayRequestError, match="invalid json"):
        _decode_success_json(r, "/x")


def test_decode_success_json_array_raises() -> None:
    r = httpx.Response(200, json=[1, 2])
    with pytest.raises(WechatPayRequestError, match="expected JSON object"):
        _decode_success_json(r, "/x")


@pytest.mark.asyncio
async def test_http_post_wraps_transport_error(v3_ctx: WechatPayV3Context) -> None:
    async def boom(*_a: object, **_k: object) -> None:
        raise httpx.ConnectError("simulated upstream refused", request=MagicMock())

    fake_client = AsyncMock()
    fake_client.post = boom
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = None

    with patch("app.integrations.wechat_pay_v3.httpx.AsyncClient", return_value=fake_client):
        with pytest.raises(WechatPayRequestError, match="network"):
            await v3_ctx._http_post("/v3/pay/transactions/jsapi", {"mchid": "x"})


@pytest.mark.asyncio
async def test_http_post_success_returns_dict(v3_ctx: WechatPayV3Context) -> None:
    fake_resp = httpx.Response(200, json={"prepay_id": "wx_ok"})
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=fake_resp)
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = None

    with patch("app.integrations.wechat_pay_v3.httpx.AsyncClient", return_value=fake_client):
        data = await v3_ctx._http_post("/v3/pay/transactions/jsapi", {"mchid": "x"})
    assert data["prepay_id"] == "wx_ok"
