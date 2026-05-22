"""微信小程序虚拟支付（xpay）单测."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from httpx import AsyncClient

from app.config import settings
from app.integrations import wechat_xpay
from app.services import payment_service


def test_calc_pay_sig_matches_hmac():
    sign_data = '{"offerId":"o1","buyQuantity":1,"env":0}'
    app_key = "test_app_key"
    expected = hmac.new(
        app_key.encode(),
        f"requestVirtualPayment&{sign_data}".encode(),
        hashlib.sha256,
    ).hexdigest()
    assert wechat_xpay.calc_pay_sig("requestVirtualPayment", sign_data, app_key) == expected


def test_calc_user_signature_matches_hmac():
    sign_data = '{"outTradeNo":"ord_abc"}'
    sk = "session_key_xyz"
    expected = hmac.new(sk.encode(), sign_data.encode(), hashlib.sha256).hexdigest()
    assert wechat_xpay.calc_user_signature(sign_data, sk) == expected


def test_build_sign_data_compact_json(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "WECHAT_XPAY_OFFER_ID", "offer123")
    monkeypatch.setattr(settings, "WECHAT_XPAY_ENV", 0)
    monkeypatch.setattr(settings, "WECHAT_XPAY_PRODUCT_MONTHLY", "prod_monthly")
    obj = wechat_xpay.build_sign_data(
        out_trade_no="ord_test01",
        plan_type="monthly",
        goods_price_cents=3900,
    )
    dumped = wechat_xpay.dumps_sign_data(obj)
    assert " " not in dumped
    parsed = json.loads(dumped)
    assert parsed["goodsPrice"] == 3900
    assert parsed["productId"] == "prod_monthly"


def test_is_xpay_order_paid():
    assert wechat_xpay.is_xpay_order_paid({"order": {"status": 2}})
    assert wechat_xpay.is_xpay_order_paid({"order": {"status": 4}})
    assert not wechat_xpay.is_xpay_order_paid({"order": {"status": 1}})


@pytest.mark.asyncio
async def test_create_order_xpay_requires_wx_login_code(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "WECHAT_PAY_MOCK_MODE", False)
    monkeypatch.setattr(settings, "WECHAT_XPAY_ENABLED", True)
    monkeypatch.setattr(settings, "WECHAT_XPAY_OFFER_ID", "offer123")
    monkeypatch.setattr(settings, "WECHAT_XPAY_APP_KEY", "key123")
    monkeypatch.setattr(settings, "WECHAT_XPAY_PRODUCT_MONTHLY", "prod_m")

    resp = await client.post(
        "/v1/payments/orders",
        headers=auth_headers,
        json={"plan_type": "monthly"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 40015


@pytest.mark.asyncio
async def test_process_xpay_goods_deliver_notify_activates_membership(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    from app.core.database import AsyncSessionLocal
    from app.models.payment import Order
    from app.models.user import User
    from sqlalchemy import select

    monkeypatch.setattr(settings, "WECHAT_PAY_MOCK_MODE", False)
    monkeypatch.setattr(settings, "WECHAT_XPAY_ENABLED", True)

    me = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    user_id = me["id"]

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        assert user is not None
        openid = user.wechat_openid or "mock_openid"
        order = Order(
            id="ord_xpay_deliver_test",
            user_id=user.id,
            plan_type="monthly",
            amount=3900,
            currency="CNY",
            status="pending",
        )
        db.add(order)
        await db.commit()

    async with AsyncSessionLocal() as db:
        ok, msg = await payment_service.process_xpay_goods_deliver_notify(
            db,
            {
                "Event": "xpay_goods_deliver_notify",
                "OutTradeNo": "ord_xpay_deliver_test",
                "OpenId": openid,
                "GoodsInfo": {"ActualPrice": 3900},
            },
        )
        assert ok, msg
        await db.commit()

    me2 = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me2["is_member"] is True

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(Order).where(Order.id == "ord_xpay_deliver_test"))
        ).scalar_one()
        assert row.status == "paid"
