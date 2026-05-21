"""W7-T1：支付与会员激活测试.

覆盖：
- 套餐列表
- 下单 → mock-confirm → 订单 paid + 会员激活
- 会员激活后配额变无限
- 会员到期惰性降级（时间旅行 monkeypatch membership_expires_at）
- 订单状态：重复支付、非 pending 支付拒绝
- 年度套餐金额、时长正确
- 续费叠加（未过期会员再次购买 → 从原到期日往后加）
- 非 mock 模式下 mock-confirm 被拒
- 无权操作他人订单
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.payment import PaymentTransaction
from app.models.user import User


def _free_user_expected_quota_totals() -> tuple[int, int]:
    """严格模式下免费额为 3/5；QUOTA_MODE=unlimited 时建配额行即为无限（-1）。"""
    if settings.QUOTA_MODE == "unlimited":
        return (-1, -1)
    return (3, 5)


# ==================== 套餐列表 ====================
@pytest.mark.asyncio
async def test_list_plans_returns_monthly_and_yearly(
    client: AsyncClient, auth_headers: dict[str, str]
):
    resp = await client.get("/v1/payments/plans", headers=auth_headers)
    assert resp.status_code == 200
    plans = resp.json()["data"]
    assert {p["plan_type"] for p in plans} == {"monthly", "yearly"}
    monthly = next(p for p in plans if p["plan_type"] == "monthly")
    yearly = next(p for p in plans if p["plan_type"] == "yearly")
    assert monthly["amount_cents"] == 3900
    assert monthly["duration_days"] == 30
    assert yearly["amount_cents"] == 29900
    assert yearly["duration_days"] == 365
    assert yearly["badge"]  # 有"立省"文案


# ==================== 下单 → mock-confirm ====================
@pytest.mark.asyncio
async def test_create_order_returns_mock_prepay_params(
    client: AsyncClient, auth_headers: dict[str, str]
):
    resp = await client.post(
        "/v1/payments/orders",
        headers=auth_headers,
        json={"plan_type": "monthly"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["mock_mode"] is True
    assert data["prepay_params"]["mock"] is True
    assert data["order"]["status"] == "pending"
    assert data["order"]["amount"] == 3900
    assert data["order"]["plan_type"] == "monthly"
    assert data["order"]["paid_at"] is None


@pytest.mark.asyncio
async def test_mock_confirm_activates_membership_and_lifts_quotas(
    client: AsyncClient, auth_headers: dict[str, str]
):
    # 先让用户产生当月分析配额 + 当日对话配额（通过 /users/me 触发 get_or_create）
    me_before = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me_before["membership_type"] == "free"
    exp_an, exp_chat = _free_user_expected_quota_totals()
    assert me_before["quota"]["analysis_total"] == exp_an
    assert me_before["quota"]["chat_total_today"] == exp_chat

    # 下单
    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]

    # mock-confirm
    confirm = await client.post(
        f"/v1/payments/orders/{order_id}/mock-confirm", headers=auth_headers
    )
    assert confirm.status_code == 200, confirm.text
    paid = confirm.json()["data"]
    assert paid["status"] == "paid"
    assert paid["paid_at"] is not None
    assert paid["membership_end"] is not None

    # /users/me 现在应该是会员 + 配额无限
    me_after = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me_after["membership_type"] == "monthly"
    assert me_after["is_member"] is True
    assert 28 <= me_after["membership_days_remaining"] <= 31
    # W8-T3：「无限」统一用 -1 表达（替代历史 9999），前端按 < 0 判断
    assert me_after["quota"]["analysis_remaining"] == -1
    assert me_after["quota"]["chat_remaining_today"] == -1
    assert me_after["quota"]["analysis_total"] == -1
    assert me_after["quota"]["chat_total_today"] == -1

    # /membership 返回一致
    mem = (
        await client.get("/v1/users/me/membership", headers=auth_headers)
    ).json()["data"]
    assert mem["is_member"] is True
    assert mem["membership_type"] == "monthly"
    assert mem["days_remaining"] >= 28


@pytest.mark.asyncio
async def test_yearly_plan_sets_expires_at_365_days_later(
    client: AsyncClient, auth_headers: dict[str, str]
):
    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "yearly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]

    await client.post(f"/v1/payments/orders/{order_id}/mock-confirm", headers=auth_headers)

    me = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me["membership_type"] == "yearly"
    # 约 365 天（允许 ±1 天的时区/跨日误差）
    assert 363 <= me["membership_days_remaining"] <= 366


# ==================== 已支付订单不可重复确认 ====================
@pytest.mark.asyncio
async def test_mock_confirm_rejects_already_paid_order(
    client: AsyncClient, auth_headers: dict[str, str]
):
    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]
    await client.post(f"/v1/payments/orders/{order_id}/mock-confirm", headers=auth_headers)

    # 再确认一次应失败
    again = await client.post(
        f"/v1/payments/orders/{order_id}/mock-confirm", headers=auth_headers
    )
    assert again.status_code == 400, again.text
    assert again.json()["code"] == 40013


# ==================== 他人订单不可操作 ====================
@pytest.mark.asyncio
async def test_cannot_confirm_another_users_order(
    client: AsyncClient, auth_headers: dict[str, str]
):
    # 用户 A 下单
    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]

    # 用户 B 登录 → 试图访问 A 的订单
    from uuid import uuid4

    login_b = await client.post(
        "/v1/auth/wechat-login", json={"code": f"pytest_{uuid4().hex}"}
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['data']['token']}"}

    confirm = await client.post(
        f"/v1/payments/orders/{order_id}/mock-confirm", headers=headers_b
    )
    # 404（订单不存在当前用户视角）
    assert confirm.status_code == 404


# ==================== 无效套餐 ====================
@pytest.mark.asyncio
async def test_create_order_rejects_unknown_plan(
    client: AsyncClient, auth_headers: dict[str, str]
):
    resp = await client.post(
        "/v1/payments/orders", headers=auth_headers, json={"plan_type": "platinum"}
    )
    assert resp.status_code in (400, 422)


# ==================== sync-from-wechat：mock 模式拒绝 ====================
@pytest.mark.asyncio
async def test_sync_from_wechat_rejected_in_mock_mode(
    client: AsyncClient, auth_headers: dict[str, str]
):
    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]
    resp = await client.post(
        f"/v1/payments/orders/{order_id}/sync-from-wechat",
        headers=auth_headers,
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == 40090


# ==================== mock 模式关闭时拒绝 mock-confirm ====================
@pytest.mark.asyncio
async def test_mock_confirm_disabled_when_mock_mode_off(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    # 先用 mock 模式下单（create_order 里还会走 mock prepay）
    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]

    # 然后关 mock 开关再去 confirm
    from app.config import settings

    monkeypatch.setattr(settings, "WECHAT_PAY_MOCK_MODE", False)
    resp = await client.post(
        f"/v1/payments/orders/{order_id}/mock-confirm", headers=auth_headers
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40013


# ==================== 续费叠加 ====================
@pytest.mark.asyncio
async def test_renew_extends_from_existing_expiry(
    client: AsyncClient, auth_headers: dict[str, str]
):
    # 第一次购买月度
    c1 = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    await client.post(
        f"/v1/payments/orders/{c1['order']['id']}/mock-confirm", headers=auth_headers
    )
    me1 = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    end1 = datetime.fromisoformat(me1["membership_expires_at"])

    # 立即再买一次月度 → 应该从原到期日往后 +30 天
    c2 = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    await client.post(
        f"/v1/payments/orders/{c2['order']['id']}/mock-confirm", headers=auth_headers
    )
    me2 = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    end2 = datetime.fromisoformat(me2["membership_expires_at"])

    delta = end2 - end1
    # 允许 ±2s 漂移
    assert abs(delta.total_seconds() - 30 * 86400) < 5


# ==================== 惰性降级 ====================
@pytest.mark.asyncio
async def test_expired_membership_auto_downgrades_on_read(
    client: AsyncClient, auth_headers: dict[str, str]
):
    # 先开会员
    c = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    await client.post(
        f"/v1/payments/orders/{c['order']['id']}/mock-confirm", headers=auth_headers
    )
    me1 = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me1["is_member"] is True

    # 直接改库：把 membership_expires_at 改到 1 小时前
    user_id = me1["id"]
    async with AsyncSessionLocal() as db:
        u = await db.get(User, user_id)
        u.membership_expires_at = datetime.now(UTC) - timedelta(hours=1)
        await db.commit()

    # 再调 /users/me → 应自动降级为 free + 配额回到 3 / 5
    me2 = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me2["is_member"] is False
    assert me2["membership_type"] == "free"
    assert me2["membership_days_remaining"] == 0
    assert me2["quota"]["analysis_total"] == 3
    assert me2["quota"]["chat_total_today"] == 5


# ==================== 订单查询 ====================
@pytest.mark.asyncio
async def test_list_and_get_my_orders(
    client: AsyncClient, auth_headers: dict[str, str]
):
    ids = []
    for plan in ("monthly", "yearly"):
        c = (
            await client.post(
                "/v1/payments/orders", headers=auth_headers, json={"plan_type": plan}
            )
        ).json()["data"]
        ids.append(c["order"]["id"])

    listing = await client.get("/v1/users/me/orders", headers=auth_headers)
    assert listing.status_code == 200
    orders = listing.json()["data"]
    assert {o["id"] for o in orders} >= set(ids)

    detail = await client.get(f"/v1/payments/orders/{ids[0]}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == ids[0]


# ==================== 支付流水 ====================
@pytest.mark.asyncio
async def test_payment_transaction_is_recorded_on_mock_pay(
    client: AsyncClient, auth_headers: dict[str, str]
):
    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]
    await client.post(f"/v1/payments/orders/{order_id}/mock-confirm", headers=auth_headers)

    async with AsyncSessionLocal() as db:
        stmt = select(PaymentTransaction).where(PaymentTransaction.order_id == order_id)
        txns = list((await db.execute(stmt)).scalars().all())
        assert len(txns) == 1
        assert txns[0].transaction_type == "payment"
        assert txns[0].amount == 3900
        assert txns[0].wechat_notify_data == {"mock": True}


# ==================== 订单超时关闭（pending → cancelled） ====================
@pytest.mark.asyncio
async def test_expire_stale_pending_orders_closes_old_pending(
    client: AsyncClient, auth_headers: dict[str, str]
):
    from sqlalchemy import text

    from app.services import payment_service

    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]
    stale_ts = datetime.now(UTC) - timedelta(hours=4)
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE orders SET created_at = :ts WHERE id = :oid"), {"ts": stale_ts, "oid": order_id})
        await db.commit()

    async with AsyncSessionLocal() as db:
        n = await payment_service.expire_stale_pending_orders(db, now=datetime.now(UTC))
        await db.commit()
    assert n >= 1

    detail = await client.get(f"/v1/payments/orders/{order_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "cancelled"


# ==================== Mock 退款记账 ====================
@pytest.mark.asyncio
async def test_mock_refund_demotes_user_and_writes_refund_txn(
    client: AsyncClient, auth_headers: dict[str, str]
):
    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]
    await client.post(f"/v1/payments/orders/{order_id}/mock-confirm", headers=auth_headers)

    refunded = await client.post(
        f"/v1/payments/orders/{order_id}/mock-refund",
        headers=auth_headers,
        params={"reason": "pytest"},
    )
    assert refunded.status_code == 200, refunded.text
    body = refunded.json()["data"]
    assert body["status"] == "refunded"

    me = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me["membership_type"] == "free"
    assert me["is_member"] is False

    async with AsyncSessionLocal() as db:
        stmt = select(PaymentTransaction).where(PaymentTransaction.order_id == order_id)
        txns = list((await db.execute(stmt)).scalars().all())
        types = sorted(t.transaction_type for t in txns)
        assert types == ["payment", "refund"]


@pytest.mark.asyncio
async def test_process_wechat_refund_notify_full_flow(
    client: AsyncClient, auth_headers: dict[str, str]
):
    from app.services import payment_service

    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]
    await client.post(f"/v1/payments/orders/{order_id}/mock-confirm", headers=auth_headers)

    payload = {
        "refund_status": "SUCCESS",
        "out_trade_no": order_id,
        "out_refund_no": "RF_utest",
        "amount": {"total": 3900, "refund": 3900, "payer_total": 3900, "payer_refund": 3900},
    }

    async with AsyncSessionLocal() as db:
        ok, msg = await payment_service.process_wechat_refund_notify(db, payload)
        assert ok, msg
        await db.commit()

    detail = await client.get(f"/v1/payments/orders/{order_id}", headers=auth_headers)
    assert detail.json()["data"]["status"] == "refunded"
    me = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me["membership_type"] == "free"

    async with AsyncSessionLocal() as db:
        ok2, _ = await payment_service.process_wechat_refund_notify(db, payload)
        assert ok2
        await db.commit()


@pytest.mark.asyncio
async def test_apply_refund_forbidden_in_mock_mode(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "WECHAT_PAY_MOCK_MODE", True)
    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]
    await client.post(f"/v1/payments/orders/{order_id}/mock-confirm", headers=auth_headers)

    resp = await client.post(
        f"/v1/payments/orders/{order_id}/apply-refund",
        headers=auth_headers,
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body.get("code") == 40090


@pytest.mark.asyncio
async def test_apply_refund_stubbed_wechat(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    """非 mock：`get_wechat_pay_v3` 打桩为假上下文，不真实连微信。"""
    from app.integrations import wechat_pay_v3 as wxpay

    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]
    await client.post(f"/v1/payments/orders/{order_id}/mock-confirm", headers=auth_headers)

    monkeypatch.setattr(settings, "WECHAT_PAY_MOCK_MODE", False)
    monkeypatch.setattr(
        settings,
        "WECHAT_PAY_NOTIFY_URL",
        "https://api.example.com/v1/payments/wechat/notify",
    )

    class _StubCtx:
        async def domestic_refund(self, **kwargs):  # noqa: ANN003
            return {"status": "PROCESSING"}

    monkeypatch.setattr(wxpay, "get_wechat_pay_v3", lambda: _StubCtx())

    resp = await client.post(f"/v1/payments/orders/{order_id}/apply-refund", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["order"]["status"] == "paid"
    assert data["wechat"]["status"] == "PROCESSING"


# ==================== sync-from-wechat：真实模式 stub 查单 ====================
@pytest.mark.asyncio
async def test_sync_from_wechat_success_marks_paid(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非 mock 路径下，`query_transaction_by_out_trade_no` 返回 SUCCESS → 订单转 paid。

    这个测试同时回归了 ``WechatPayV3Context.query_transaction_by_out_trade_no``
    必须存在的契约——历史 bug 是 service 调用了不存在的方法，触发 AttributeError
    被兜底成"签名或商户证书配置异常"，客户端付款成功后查单一直报错。
    """
    from app.integrations import wechat_pay_v3 as wxpay

    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]
    amount_cents = int(create["order"]["amount"])

    monkeypatch.setattr(settings, "WECHAT_PAY_MOCK_MODE", False)

    class _StubCtx:
        async def query_transaction_by_out_trade_no(self, out_trade_no: str):
            assert out_trade_no == order_id
            return {
                "trade_state": "SUCCESS",
                "transaction_id": "4200001234202611210000000001",
                "amount": {"total": amount_cents, "currency": "CNY"},
            }

    monkeypatch.setattr(wxpay, "get_wechat_pay_v3", lambda: _StubCtx())

    resp = await client.post(
        f"/v1/payments/orders/{order_id}/sync-from-wechat", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["order"]["status"] == "paid"


# ==================== 关闭自动续费（docs/02 §6.5） ====================
@pytest.mark.asyncio
async def test_cancel_auto_renew_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/v1/payments/membership/cancel-auto-renew")
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_cancel_auto_renew_turns_off_flag(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """mock 模式下先 enable auto_renew，再调 cancel 端点关闭，DB 持久化。"""
    monkeypatch.setattr(settings, "WECHAT_PAY_MOCK_MODE", True)

    # 先开启自动续费（mock 模式直接落库 True）
    on = await client.post(
        "/v1/payments/auto-renew", headers=auth_headers, json={"enabled": True}
    )
    assert on.status_code == 200, on.text
    assert on.json()["data"]["auto_renew"] is True

    # 调 cancel
    off = await client.post(
        "/v1/payments/membership/cancel-auto-renew", headers=auth_headers
    )
    assert off.status_code == 200, off.text
    body = off.json()
    assert body["code"] == 0
    assert body["data"]["auto_renew"] is False
    # 没买会员，expires_at 为 None；message 不应含到期日
    assert "已关闭自动续费" in body["message"]

    # 持久化校验
    async with AsyncSessionLocal() as db:
        me = (
            await db.execute(
                select(User).where(User.wechat_openid.is_not(None)).order_by(User.created_at.desc())
            )
        ).scalars().first()
        assert me is not None
        assert me.auto_renew is False


@pytest.mark.asyncio
async def test_cancel_auto_renew_message_includes_expiry(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """有 expires_at 的会员调 cancel，message 应含 YYYY-MM-DD."""
    monkeypatch.setattr(settings, "WECHAT_PAY_MOCK_MODE", True)

    # 下单 + mock-confirm 激活会员（拿到真实 expires_at）
    create = (
        await client.post(
            "/v1/payments/orders", headers=auth_headers, json={"plan_type": "monthly"}
        )
    ).json()["data"]
    order_id = create["order"]["id"]
    await client.post(
        f"/v1/payments/orders/{order_id}/mock-confirm", headers=auth_headers
    )

    # auto-renew 打开
    await client.post(
        "/v1/payments/auto-renew", headers=auth_headers, json={"enabled": True}
    )

    off = await client.post(
        "/v1/payments/membership/cancel-auto-renew", headers=auth_headers
    )
    assert off.status_code == 200, off.text
    body = off.json()
    assert body["data"]["auto_renew"] is False
    assert body["data"]["expires_at"] is not None
    assert "已关闭自动续费，当前会员有效期至 " in body["message"]
