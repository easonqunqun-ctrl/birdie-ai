"""支付与会员激活服务。

W7-T1 设计要点：
- `WECHAT_PAY_MOCK_MODE=True`（默认）时，整条链路走本地 mock：
  `create_order` → 立即返回 `prepay_params={mock: True}`；客户端展示模拟弹窗后
  调 `POST /payments/orders/{id}/mock-confirm`，后端直接 `paid` + 激活会员。
- 真实模式的接入点保留在 `_create_wechat_prepay` / `_handle_wechat_notify`，
  W8 商户号落地时只需把 NotImplementedError 换成真实 WechatPayV3 SDK 调用。
- 会员激活统一由 `activate_membership` 完成，顺便**刷新当月/当日配额**为无限，
  保证用户购买会员后立即可以无限分析/对话（不用等下个月新配额行生成）。
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AppException, BadRequestError, ConflictError, NotFoundError, ThirdPartyError
from app.core.security import new_id
from app.integrations import wechat_pay_v3, wechat_xpay
from app.integrations.wechat import code2session
from app.models.analysis import AnalysisQuota
from app.models.chat import ChatQuota
from app.models.payment import Order, PaymentTransaction
from app.models.user import User
from app.schemas.payment import PlanOption, PrepayParams

logger = structlog.get_logger("payment_service")

# ==================== 套餐价格表 ====================
# 分（cents）；与 docs/01 §8.1 对齐
PLAN_PRICING: dict[str, dict] = {
    "monthly": {
        "name": "月度会员",
        "amount_cents": 3900,
        "amount_yuan_display": "¥39",
        "duration_days": 30,
        "badge": None,
    },
    "yearly": {
        "name": "年度会员",
        "amount_cents": 29900,
        "amount_yuan_display": "¥299",
        "duration_days": 365,
        "badge": "相当于每月 ¥24.9，立省 ¥169",
    },
    # "family" 套餐 W7 不开；schema PlanType 里也不列
}


class PaymentNotAllowedError(AppException):
    """支付相关的业务状态冲突（订单已支付/已取消等）."""

    code = 40013
    http_status = 400
    message = "订单状态不允许本次操作"


def list_plans() -> list[PlanOption]:
    return [
        PlanOption(plan_type=pt, **info)  # type: ignore[arg-type]
        for pt, info in PLAN_PRICING.items()
    ]


def virtual_pay_enabled() -> bool:
    """非 mock 且显式开启 xpay 时，小程序走虚拟支付而非 JSAPI。"""
    return bool(
        getattr(settings, "WECHAT_XPAY_ENABLED", False)
        and not settings.WECHAT_PAY_MOCK_MODE
    )


# ==================== 下单 ====================
async def create_order(
    db: AsyncSession,
    user: User,
    plan_type: str,
    *,
    wx_login_code: str | None = None,
) -> tuple[Order, PrepayParams]:
    """创建订单 + 返回 prepay 参数（mock 模式下仅含 mock=True）."""
    if plan_type not in PLAN_PRICING:
        raise BadRequestError(code=40001, message=f"不支持的套餐：{plan_type}")

    pricing = PLAN_PRICING[plan_type]

    order = Order(
        id=new_id("ord"),
        user_id=user.id,
        plan_type=plan_type,
        amount=pricing["amount_cents"],
        currency="CNY",
        status="pending",
    )
    db.add(order)
    await db.flush()
    # 拉齐 server_default（created_at 等），避免长时间微信请求后 ORM 上仍是 None →
    # ``OrderResponse`` 校验失败触发 ``ResponseValidationError``（易被 broad Exception 兜底成 500）。
    await db.refresh(order)

    if settings.WECHAT_PAY_MOCK_MODE:
        prepay = PrepayParams(mock=True, payment_method="mock")
    elif virtual_pay_enabled():
        prepay = await _create_xpay_virtual_prepay(
            db, order, user, wx_login_code=wx_login_code
        )
    else:
        prepay = await _create_wechat_prepay(db, order, user)

    return order, prepay


async def _create_xpay_virtual_prepay(
    db: AsyncSession,
    order: Order,
    user: User,
    *,
    wx_login_code: str | None,
) -> PrepayParams:
    """虚拟支付：组装 signData + paySig + signature 供 wx.requestVirtualPayment。"""
    if not (wx_login_code and wx_login_code.strip()):
        raise BadRequestError(
            code=40015,
            message="虚拟支付需要微信登录凭证，请重试",
        )
    if not (user.wechat_openid and user.wechat_openid.strip()):
        raise BadRequestError(
            code=40014,
            message="需在微信内使用小程序完成支付，无法获取 openid",
        )

    try:
        session = await code2session(wx_login_code.strip())
    except AppException:
        raise
    except Exception as e:
        logger.exception("xpay_code2session_failed", error=str(e), order_id=order.id)
        raise ThirdPartyError(message="微信登录失败，请重试", detail=str(e)) from e

    if session.openid != user.wechat_openid:
        raise BadRequestError(
            code=40016,
            message="微信账号与当前登录用户不一致，请重新登录",
        )

    try:
        params = wechat_xpay.build_virtual_prepay_params(
            out_trade_no=order.id,
            plan_type=order.plan_type,
            goods_price_cents=order.amount,
            session_key=session.session_key,
        )
    except (RuntimeError, BadRequestError):
        raise
    except Exception as e:
        logger.exception("xpay_build_prepay_failed", error=str(e), order_id=order.id)
        raise ThirdPartyError(message="虚拟支付签名失败", detail=str(e)) from e

    order.wechat_prepay_id = f"xpay:{order.plan_type}"
    await db.flush()

    return PrepayParams(
        mock=False,
        payment_method="virtual",
        sign_data=params["sign_data"],
        pay_sig=params["pay_sig"],
        signature=params["signature"],
        mode=params["mode"],
    )


async def _create_wechat_prepay(db: AsyncSession, order: Order, user: User) -> PrepayParams:
    """真实微信 JSAPI 下单 + 返回小程序 `wx.requestPayment` 参数."""
    if not (user.wechat_openid and user.wechat_openid.strip()):
        raise BadRequestError(
            code=40014,
            message="需在微信内使用小程序完成支付，无法获取 openid",
        )
    try:
        ctx = wechat_pay_v3.get_wechat_pay_v3()
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning("wechat_pay_v3_init_failed_create_prepay", error=str(e), order_id=order.id)
        raise ThirdPartyError(message=f"支付配置错误：{e!s}", detail=str(e)) from e

    pricing = PLAN_PRICING[order.plan_type]
    prepay_id = ""
    try:
        prepay_id = await ctx.create_jsapi_order(
            out_trade_no=order.id,
            openid=user.wechat_openid,
            amount_cents=order.amount,
            description=str(pricing["name"]),
        )
    except wechat_pay_v3.WechatPayRequestError as e:
        raise ThirdPartyError(message="微信支付下单失败", detail=str(e)) from e
    except Exception as e:
        # 签名 / 商户私钥损坏 / cryptography 等非 HTTP 错误若不放行，会变成全局 500「服务内部错误」
        logger.exception(
            "wechat_jsapi_prepay_unexpected",
            error=str(e),
            order_id=order.id,
        )
        raise ThirdPartyError(
            message="发起支付失败：请核对商户 API 证书、序列号与私钥是否匹配",
            detail=str(e),
        ) from e

    if not prepay_id:
        raise ThirdPartyError(message="微信支付未返回 prepay_id")

    order.wechat_prepay_id = prepay_id
    await db.flush()
    try:
        return ctx.build_miniprogram_prepay(prepay_id).model_copy(
            update={"payment_method": "jsapi", "mock": False}
        )
    except Exception as e:
        logger.exception(
            "wechat_build_miniprogram_prepay_failed",
            error=str(e),
            order_id=order.id,
        )
        raise ThirdPartyError(
            message="生成支付签名失败：请核对商户 API 证书与 WECHAT_PAY_MCH_SERIAL",
            detail=str(e),
        ) from e


# ==================== mock-confirm ====================
async def mock_confirm_payment(db: AsyncSession, order: Order, user: User) -> Order:
    """Mock 模式专用：立即标记订单已支付并激活会员。"""
    if not settings.WECHAT_PAY_MOCK_MODE:
        raise PaymentNotAllowedError(message="mock-confirm 仅在 mock 模式下可用")
    if order.status == "paid":
        raise PaymentNotAllowedError(message="订单已支付")
    if order.status != "pending":
        raise PaymentNotAllowedError(message=f"订单状态 {order.status} 不允许支付")
    if order.user_id != user.id:
        raise ConflictError(code=40301, message="无权操作此订单")

    await _mark_paid(db, order, user, transaction_id=f"mock_{order.id}", notify_data={"mock": True})
    return order


# ==================== 通用：标记已支付 + 激活会员 ====================
async def _mark_paid(
    db: AsyncSession,
    order: Order,
    user: User,
    *,
    transaction_id: str,
    notify_data: dict | None = None,
) -> None:
    """订单置 paid 状态 + 激活 / 续期会员 + 写支付流水 + 刷新当前配额。"""
    now = datetime.now(UTC)
    pricing = PLAN_PRICING[order.plan_type]
    duration = timedelta(days=pricing["duration_days"])

    # 续期策略：若用户当前仍是有效会员（未过期），从到期时间往后叠加；
    # 若已过期或免费用户，则从当前时间起算
    base = user.membership_expires_at
    if base is None or base <= now:
        base = now

    new_end = base + duration
    membership_start = now if (user.membership_expires_at is None or user.membership_expires_at <= now) else user.membership_started_at or now

    order.status = "paid"
    order.paid_at = now
    order.wechat_transaction_id = transaction_id
    order.membership_start = membership_start
    order.membership_end = new_end

    # 激活/续期用户会员
    user.membership_type = order.plan_type if order.plan_type in ("monthly", "yearly", "family") else "monthly"
    user.membership_started_at = membership_start
    user.membership_expires_at = new_end

    # 刷新当月/当日配额为"无限"（-1），让用户立即享受权益
    await _lift_current_quotas_to_unlimited(db, user)

    # 写支付流水
    txn = PaymentTransaction(
        id=new_id("ptx"),
        order_id=order.id,
        user_id=user.id,
        transaction_type="payment",
        amount=order.amount,
        wechat_notify_data=notify_data or {},
    )
    db.add(txn)
    await db.flush()


async def _lift_current_quotas_to_unlimited(db: AsyncSession, user: User) -> None:
    """把用户当月分析 + 当日对话配额的 total 抬到 -1（无限）."""
    now_cn = datetime.now(UTC) + timedelta(hours=8)
    month_str = now_cn.strftime("%Y-%m")
    today_cn = now_cn.date()

    a_q = (
        await db.execute(
            select(AnalysisQuota).where(
                AnalysisQuota.user_id == user.id,
                AnalysisQuota.quota_month == month_str,
            )
        )
    ).scalar_one_or_none()
    if a_q is not None:
        a_q.total = -1

    c_q = (
        await db.execute(
            select(ChatQuota).where(
                ChatQuota.user_id == user.id,
                ChatQuota.quota_date == today_cn,
            )
        )
    ).scalar_one_or_none()
    if c_q is not None:
        c_q.total = -1

    await db.flush()


async def grant_complimentary_membership(
    db: AsyncSession,
    user: User,
    *,
    duration_days: int,
    plan_type: str = "yearly",
) -> datetime:
    """运营/BD 赠送会员（无订单）；续期策略与 ``_mark_paid`` 一致."""

    if plan_type not in {"monthly", "yearly", "family"}:
        raise BadRequestError(code=40001, message=f"不支持的套餐：{plan_type}")
    now = datetime.now(UTC)
    base = user.membership_expires_at
    if base is None or base <= now:
        base = now
    new_end = base + timedelta(days=duration_days)
    if user.membership_expires_at is None or user.membership_expires_at <= now:
        user.membership_started_at = now
    user.membership_type = plan_type
    user.membership_expires_at = new_end
    await _lift_current_quotas_to_unlimited(db, user)
    await db.flush()
    return new_end


# ==================== 会员状态读取 ====================
def is_member(user: User, *, now: datetime | None = None) -> bool:
    """判断当前是否为**有效**会员。纯函数，不写库。"""
    if user.membership_type == "free":
        return False
    if user.membership_expires_at is None:
        return False
    reference = now or datetime.now(UTC)
    return user.membership_expires_at > reference


def days_remaining(user: User, *, now: datetime | None = None) -> int:
    if not is_member(user, now=now):
        return 0
    reference = now or datetime.now(UTC)
    remaining = (user.membership_expires_at - reference).total_seconds() / 86400  # type: ignore[operator]
    return max(0, int(remaining) + (1 if remaining - int(remaining) > 0 else 0))


async def ensure_membership_valid(db: AsyncSession, user: User) -> bool:
    """懒检查：若用户会员已过期 → 降级为 free + 把当月/当日配额回到免费额度。

    返回 True 表示发生了降级（调用方需要 commit）；False 表示无变化。
    被 `get_user_by_id` / `get_current_user` 在读取用户时调用，
    避免依赖定时任务。
    """
    if user.membership_type == "free":
        return False
    if user.membership_expires_at is None:
        # 异常状态：非 free 但没到期时间，保守修复为 free
        user.membership_type = "free"
        return True
    if user.membership_expires_at > datetime.now(UTC):
        return False

    # 已过期：降级
    expired_at = user.membership_expires_at
    user.membership_type = "free"
    user.auto_renew = False

    # 当月/当日配额若为无限，回落到免费用户额度
    now_cn = datetime.now(UTC) + timedelta(hours=8)
    month_str = now_cn.strftime("%Y-%m")
    today_cn = now_cn.date()

    a_q = (
        await db.execute(
            select(AnalysisQuota).where(
                AnalysisQuota.user_id == user.id,
                AnalysisQuota.quota_month == month_str,
            )
        )
    ).scalar_one_or_none()
    if a_q is not None and a_q.total < 0:
        a_q.total = settings.FREE_USER_MONTHLY_ANALYSES

    c_q = (
        await db.execute(
            select(ChatQuota).where(
                ChatQuota.user_id == user.id,
                ChatQuota.quota_date == today_cn,
            )
        )
    ).scalar_one_or_none()
    if c_q is not None and c_q.total < 0:
        c_q.total = settings.FREE_USER_DAILY_CHATS

    await db.flush()

    mini_openid = user.wechat_openid
    if mini_openid:
        try:
            from app.integrations.wechat_subscribe_message import (
                send_membership_expired_notification,
            )

            await send_membership_expired_notification(
                openid=mini_openid,
                expired_at=expired_at,
            )
        except Exception as exc:
            logger.warning(
                "membership_expired_subscribe_notify_failed",
                user_id=user.id,
                error=str(exc),
            )

    return True


# ==================== 查询 ====================
async def get_order(db: AsyncSession, order_id: str, user: User) -> Order:
    order = await db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise NotFoundError(code=40401, message="订单不存在")
    return order


async def list_user_orders(db: AsyncSession, user: User, limit: int = 20) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


# ==================== 微信支付回调 ====================
async def process_wechat_payment_notify(
    db: AsyncSession,
    notify_data: dict,
) -> tuple[bool, str]:
    """处理微信 `transaction` 解密后的通知。返回 (ok, message)。"""
    if settings.WECHAT_PAY_MOCK_MODE:
        return False, "mock 模式不应收到真实回调"

    if notify_data.get("trade_state") != "SUCCESS":
        return True, "非成功态，略过"

    out_no = notify_data.get("out_trade_no")
    txn_id = notify_data.get("transaction_id") or ""
    if not out_no:
        return False, "缺少 out_trade_no"

    order = await db.get(Order, out_no)
    if order is None:
        return False, "订单不存在"

    amt = notify_data.get("amount")
    if (
        isinstance(amt, dict)
        and amt.get("total") is not None
        and int(amt["total"]) != order.amount
    ):
        return False, "订单金额与通知不一致"

    if order.status == "paid":
        return True, "已支付，幂等"

    user = await db.get(User, order.user_id)
    if user is None:
        return False, "用户不存在"

    await _mark_paid(
        db,
        order,
        user,
        transaction_id=txn_id,
        notify_data=notify_data,
    )
    return True, "ok"


async def sync_pending_order_from_wechat(
    db: AsyncSession,
    order_id: str,
    user: User,
) -> tuple[bool, Order, str]:
    """对已登录用户名下的 pending 订单，调用微信「查单」若 SUCCESS 则执行与回调相同的到账逻辑。

    返回 (是否在**本次调用**中新完成到账, order, detail).
    mock 模式下不可用；已 paid 幂等返回 synced=False。
    """
    order = await get_order(db, order_id, user)
    if settings.WECHAT_PAY_MOCK_MODE:
        raise BadRequestError(code=40090, message="mock 模式下请使用 mock-confirm")

    if order.status == "paid":
        await db.refresh(order)
        return False, order, "already_paid"

    if order.status != "pending":
        raise PaymentNotAllowedError(message=f"仅待支付订单可同步，当前 {order.status}")

    if virtual_pay_enabled():
        return await _sync_pending_order_from_xpay(db, order, user)

    try:
        ctx = wechat_pay_v3.get_wechat_pay_v3()
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning("wechat_pay_v3_init_failed_sync_order", error=str(e), order_id=order.id)
        raise ThirdPartyError(message=f"支付配置错误：{e!s}", detail=str(e)) from e

    try:
        data = await ctx.query_transaction_by_out_trade_no(order.id)
    except wechat_pay_v3.WechatPayRequestError as e:
        raise ThirdPartyError(message="微信查单失败", detail=str(e)) from e
    except Exception as e:
        logger.exception(
            "wechat_query_transaction_unexpected",
            error=str(e),
            order_id=order.id,
        )
        raise ThirdPartyError(
            message="微信查单失败：签名或商户证书配置异常",
            detail=str(e),
        ) from e

    trade_state = (data.get("trade_state") or "").upper()
    if trade_state != "SUCCESS":
        return False, order, f"wechat_trade_state={trade_state or 'UNKNOWN'}"

    txn_id = str(data.get("transaction_id") or "")
    amt = data.get("amount")
    if (
        isinstance(amt, dict)
        and amt.get("total") is not None
        and int(amt["total"]) != order.amount
    ):
        raise BadRequestError(code=40091, message="微信订单金额与本系统订单不一致，已拒绝入账")

    await db.refresh(order)
    if order.status == "paid":
        return False, order, "already_paid"

    u = await db.get(User, order.user_id)
    if u is None:
        raise NotFoundError(code=40402, message="用户不存在")

    await _mark_paid(
        db,
        order,
        u,
        transaction_id=txn_id or "wechat_sync",
        notify_data={"source": "query_out_trade_no", "raw_keys": list(data.keys())[:20]},
    )
    await db.refresh(order)
    return True, order, "synced_from_wechat"


async def _sync_pending_order_from_xpay(
    db: AsyncSession,
    order: Order,
    user: User,
) -> tuple[bool, Order, str]:
    if not (user.wechat_openid and user.wechat_openid.strip()):
        raise BadRequestError(code=40014, message="缺少 openid，无法查单")

    try:
        data = await wechat_xpay.query_order(
            openid=user.wechat_openid.strip(),
            order_id=order.id,
        )
    except ThirdPartyError:
        raise
    except Exception as e:
        logger.exception("xpay_query_order_unexpected", error=str(e), order_id=order.id)
        raise ThirdPartyError(message="虚拟支付查单失败", detail=str(e)) from e

    if not wechat_xpay.is_xpay_order_paid(data):
        wx_order = data.get("order") if isinstance(data.get("order"), dict) else {}
        st = wx_order.get("status", "UNKNOWN")
        return False, order, f"xpay_status={st}"

    wx_order = data.get("order") if isinstance(data.get("order"), dict) else {}
    paid_fee = wx_order.get("paid_fee")
    if paid_fee is not None and int(paid_fee) != order.amount:
        raise BadRequestError(code=40091, message="虚拟支付订单金额与本系统订单不一致，已拒绝入账")

    await db.refresh(order)
    if order.status == "paid":
        return False, order, "already_paid"

    u = await db.get(User, order.user_id)
    if u is None:
        raise NotFoundError(code=40402, message="用户不存在")

    txn_id = str(
        wx_order.get("wxpay_order_id")
        or wx_order.get("channel_order_id")
        or wx_order.get("wx_order_id")
        or "xpay_sync"
    )

    await _mark_paid(
        db,
        order,
        u,
        transaction_id=txn_id,
        notify_data={"source": "xpay_query_order", "raw_keys": list(wx_order.keys())[:20]},
    )
    await db.refresh(order)
    return True, order, "synced_from_xpay"


async def process_xpay_goods_deliver_notify(
    db: AsyncSession,
    payload: dict[str, Any],
) -> tuple[bool, str]:
    """处理 xpay_goods_deliver_notify 消息推送（用户已支付，需发货/激活会员）。"""
    if not virtual_pay_enabled():
        return False, "xpay_not_enabled"

    out_no = str(payload.get("OutTradeNo") or payload.get("out_trade_no") or "").strip()
    if not out_no:
        return False, "missing_out_trade_no"

    order = await db.get(Order, out_no)
    if order is None:
        return False, "order_not_found"

    if order.status == "paid":
        return True, "already_paid_idempotent"

    if order.status != "pending":
        return False, f"unexpected_status_{order.status}"

    goods = payload.get("GoodsInfo") or payload.get("goods_info") or {}
    if isinstance(goods, dict):
        actual = goods.get("ActualPrice") or goods.get("actual_price")
        if actual is not None and int(actual) != order.amount:
            return False, "amount_mismatch"

    open_id = str(payload.get("OpenId") or payload.get("openid") or "").strip()
    user = await db.get(User, order.user_id)
    if user is None:
        return False, "user_not_found"
    if open_id and user.wechat_openid and open_id != user.wechat_openid:
        return False, "openid_mismatch"

    wx_pay = payload.get("WeChatPayInfo") or payload.get("we_chat_pay_info") or {}
    txn_id = "xpay_deliver"
    if isinstance(wx_pay, dict):
        txn_id = str(
            wx_pay.get("TransactionId")
            or wx_pay.get("transaction_id")
            or wx_pay.get("MchOrderNo")
            or txn_id
        )

    await _mark_paid(
        db,
        order,
        user,
        transaction_id=txn_id,
        notify_data={"source": "xpay_goods_deliver_notify", "event_keys": list(payload.keys())[:20]},
    )
    return True, "ok"


def refund_out_no_for_order(order_id: str) -> str:
    """稳定的商户退款单号（单笔订单多次重试仍为同一串，微信侧 DUPLICATE 可查）."""
    cand = "".join(c for c in order_id if c.isalnum() or c == "_") or "ord"
    return ("RF_" + cand)[:64]


async def apply_wechat_refund_for_order(
    db: AsyncSession,
    order: Order,
    user: User,
    *,
    reason: str | None = None,
) -> tuple[dict[str, Any], Order]:
    """非 mock：向微信申请全额退款；在退款 NOTIFY 到来前本地订单仍为 paid."""
    if settings.WECHAT_PAY_MOCK_MODE:
        raise BadRequestError(code=40090, message="mock 模式下请使用 POST .../mock-refund")
    if order.user_id != user.id:
        raise ConflictError(code=40301, message="无权操作此订单")
    if order.status != "paid":
        raise PaymentNotAllowedError(message=f"仅已支付订单可申请退款（当前 {order.status}）")

    win = getattr(settings, "PAYMENT_SELF_REFUND_WINDOW_HOURS", 24)
    paid_at = order.paid_at
    if paid_at is not None and int(win or 0) > 0:
        last_ok = paid_at + timedelta(hours=int(win))
        if datetime.now(UTC) > last_ok:
            raise BadRequestError(
                code=40094,
                message="已超过自助退款时限，如需协助请联系客服",
            )

    notify_url = wechat_pay_v3.resolve_wechat_pay_refund_notify_url()
    if not notify_url.strip():
        raise ThirdPartyError(
            message="未配置 WECHAT_PAY_REFUND_NOTIFY_URL，且无法在 WECHAT_PAY_NOTIFY_URL 上推导退款回调",
        )

    try:
        ctx = wechat_pay_v3.get_wechat_pay_v3()
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning("wechat_pay_v3_init_failed_refund", error=str(e), order_id=order.id)
        raise ThirdPartyError(message=f"支付配置错误：{e!s}", detail=str(e)) from e

    try:
        wx = await ctx.domestic_refund(
            out_trade_no=order.id,
            out_refund_no=refund_out_no_for_order(order.id),
            refund_cents=int(order.amount),
            total_cents=int(order.amount),
            notify_url=notify_url.strip(),
            reason=reason,
        )
    except wechat_pay_v3.WechatPayRequestError as e:
        logger.warning("wechat_domestic_refund_failed", order_id=order.id, detail=str(e))
        raise ThirdPartyError(message="微信退款接口调用失败", detail=str(e)) from e

    await db.refresh(order)
    return wx, order


async def process_wechat_refund_notify(db: AsyncSession, refund_payload: dict) -> tuple[bool, str]:
    """处理退款异步通知解密 JSON；SUCCESS ⇒ `refunded` + 降级会员."""
    rs = str(refund_payload.get("refund_status") or "").strip().upper()
    if rs != "SUCCESS":
        return True, "non_success_ignore"

    out_trade_no = refund_payload.get("out_trade_no")
    if not out_trade_no:
        return False, "missing_out_trade_no"

    order = await db.get(Order, str(out_trade_no))
    if order is None:
        return False, "order_not_found"
    if order.status == "refunded":
        return True, "already_refunded_idempotent"
    if order.status != "paid":
        return False, f"unexpected_local_status_{order.status}"

    amt = refund_payload.get("amount")
    if not isinstance(amt, dict):
        return False, "bad_amount_payload"
    total_raw = amt.get("payer_total")
    refund_raw = amt.get("payer_refund")
    if total_raw is None:
        total_raw = amt.get("total")
    if refund_raw is None:
        refund_raw = amt.get("refund")
    try:
        total_i = int(total_raw)  # type: ignore[arg-type]
        ref_i = int(refund_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False, "amount_not_integers"
    if total_i != int(order.amount) or ref_i != int(order.amount):
        return False, "amount_not_full_refund_guard"

    user = await db.get(User, order.user_id)
    if user is None:
        return False, "user_not_found"

    await _demote_membership_after_mock_refund(db, user)
    rid = refund_payload.get("out_refund_no") or refund_payload.get("refund_id") or ""
    rr = (
        refund_payload.get("user_received_account")
        or refund_payload.get("remark")
        or (str(rid).strip() or "wechat_refund_notify")
    )
    if isinstance(rr, str) and len(rr) > 500:
        rr = rr[:500]

    ts = datetime.now(UTC)
    order.status = "refunded"
    order.refunded_at = ts
    order.refund_reason = rr if isinstance(rr, str) else "wechat_refund_notify"

    txn = PaymentTransaction(
        id=new_id("ptx"),
        order_id=order.id,
        user_id=user.id,
        transaction_type="refund",
        amount=order.amount,
        wechat_notify_data=refund_payload,
    )
    db.add(txn)
    await db.flush()

    return True, "ok"


async def expire_stale_pending_orders(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    """将超过阈值的 pending 订单置为 cancelled。

    Celery：`xiaoniao.expire_stale_pending_orders` 定期触发；不写支付流水。"""
    ref = now or datetime.now(UTC)
    ttl = settings.PAYMENT_PENDING_ORDER_EXPIRE_MINUTES
    if ttl <= 0:
        return 0
    cutoff = ref - timedelta(minutes=ttl)
    res = await db.execute(
        update(Order)
        .where(Order.status == "pending", Order.created_at < cutoff)
        .values(status="cancelled")
        .execution_options(synchronize_session=False)
    )
    return int(res.rowcount or 0)


async def _demote_membership_after_mock_refund(db: AsyncSession, user: User) -> None:
    """Mock 全额退款演练：清零会员与配额（与多次续费等 edge case 解耦）。"""
    user.membership_type = "free"
    user.membership_started_at = None
    user.membership_expires_at = None
    user.auto_renew = False
    user.papay_contract_id = None

    now_cn = datetime.now(UTC) + timedelta(hours=8)
    month_str = now_cn.strftime("%Y-%m")
    today_cn = now_cn.date()

    a_q = (
        await db.execute(
            select(AnalysisQuota).where(
                AnalysisQuota.user_id == user.id,
                AnalysisQuota.quota_month == month_str,
            )
        )
    ).scalar_one_or_none()
    if a_q is not None and a_q.total < 0:
        a_q.total = settings.FREE_USER_MONTHLY_ANALYSES

    c_q = (
        await db.execute(
            select(ChatQuota).where(
                ChatQuota.user_id == user.id,
                ChatQuota.quota_date == today_cn,
            )
        )
    ).scalar_one_or_none()
    if c_q is not None and c_q.total < 0:
        c_q.total = settings.FREE_USER_DAILY_CHATS

    await db.flush()


async def mock_refund_paid_order(
    db: AsyncSession,
    order: Order,
    user: User,
    *,
    reason: str | None = None,
) -> Order:
    """Mock 模式下：对已支付订单做全额退款记账 + 将会员降为免费。"""
    if not settings.WECHAT_PAY_MOCK_MODE:
        raise PaymentNotAllowedError(message="mock 退款仅在 WECHAT_PAY_MOCK_MODE 下可用")
    if order.status != "paid":
        raise PaymentNotAllowedError(message=f"仅已支付订单可退款（当前 {order.status}）")
    if order.user_id != user.id:
        raise ConflictError(code=40301, message="无权操作此订单")

    rid = reason.strip() if reason and reason.strip() else "mock_refund"
    ts = datetime.now(UTC)

    await _demote_membership_after_mock_refund(db, user)

    order.status = "refunded"
    order.refunded_at = ts
    order.refund_reason = rid

    txn = PaymentTransaction(
        id=new_id("ptx"),
        order_id=order.id,
        user_id=user.id,
        transaction_type="refund",
        amount=order.amount,
        wechat_notify_data={"mock": True, "reason": rid},
    )
    db.add(txn)
    await db.flush()
    return order


async def apply_auto_renew(
    db: AsyncSession,
    user: User,
    *,
    enabled: bool,
    redis: Redis | None = None,
) -> dict[str, Any] | None:
    """更新自动续费意向。

    - 关闭：仅写 `auto_renew=False`；
    - mock 开通：直接 `auto_renew=True`；
    - 真实开通：返回 ``papay`` 跳转参数（不立即改 auto_renew，等签约 notify）。
    """
    import secrets
    from zoneinfo import ZoneInfo

    from app.core.redis import get_redis

    if not enabled:
        user.auto_renew = False
        await db.flush()
        return None

    if settings.WECHAT_PAY_MOCK_MODE:
        user.auto_renew = True
        await db.flush()
        return None

    if virtual_pay_enabled():
        raise BadRequestError(
            code=40098,
            message="虚拟支付模式下暂不支持委托代扣自动续费，请手动续费",
        )

    if not (user.wechat_openid and user.wechat_openid.strip()):
        raise BadRequestError(
            code=40014,
            message="需在微信内完成签约以获取 openid",
        )

    plan_id = int(settings.WECHAT_PAY_PAPAY_PLAN_ID or 0)
    if plan_id <= 0:
        raise BadRequestError(
            code=40096,
            message="商户未开通委托代扣或未配置 WECHAT_PAY_PAPAY_PLAN_ID",
        )
    notify = (settings.WECHAT_PAY_PAPAY_NOTIFY_URL or "").strip()
    if not notify:
        raise BadRequestError(
            code=40097,
            message="未配置 WECHAT_PAY_PAPAY_NOTIFY_URL",
        )

    try:
        ctx = wechat_pay_v3.get_wechat_pay_v3()
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning("wechat_pay_v3_init_failed_papay", error=str(e), user_id=user.id)
        raise ThirdPartyError(message=f"支付配置错误：{e!s}", detail=str(e)) from e

    out_contract_code = secrets.token_hex(16)
    cn = ZoneInfo("Asia/Shanghai")
    now_cn = datetime.now(UTC).astimezone(cn)
    est = (now_cn + timedelta(days=2)).date().isoformat()

    display_base = (user.nickname or "领翼用户").strip() or "领翼用户"
    display = display_base[:32]

    try:
        data = await ctx.papay_pre_entrust_mini_program(
            openid=user.wechat_openid.strip(),
            plan_id=plan_id,
            out_contract_code=out_contract_code,
            contract_display_account=display,
            contract_notify_url=notify,
            estimated_deduct_date=est,
            estimated_deduct_total=int(PLAN_PRICING["monthly"]["amount_cents"]),
            description="领翼golf会员自动续费",
        )
    except wechat_pay_v3.WechatPayRequestError as e:
        logger.warning("papay_pre_entrust_failed", user_id=user.id, detail=str(e))
        raise ThirdPartyError(message="微信预签约失败", detail=str(e)) from e

    r = redis if redis is not None else await get_redis()
    await r.set(f"papay:occ:{out_contract_code}", user.id, ex=900)

    pid = str(data.get("pre_entrustweb_id") or "")
    aid = str(data.get("redirect_appid") or "")
    rpath = str(data.get("redirect_path") or "")
    if not pid or not aid or not rpath:
        raise ThirdPartyError(message="微信预签约返回不完整", detail=str(data)[:500])
    return {
        "pre_entrustweb_id": pid,
        "redirect_appid": aid,
        "redirect_path": rpath,
    }


async def process_papay_contract_notify(db: AsyncSession, payload: dict[str, Any]) -> tuple[bool, str]:
    """解析委托代扣签约 notify（MVP：优先平文本 JSON；字段名随微信文档演进做宽容读取）。"""
    from app.core.redis import get_redis

    out_code = str(
        payload.get("out_contract_code")
        or payload.get("OutContractCode")
        or "",
    ).strip()
    cid = str(payload.get("contract_id") or payload.get("contractId") or "").strip()
    if not out_code and not cid:
        return False, "missing_contract_reference"

    redis = await get_redis()
    user: User | None = None
    if out_code:
        raw_uid = await redis.get(f"papay:occ:{out_code}")
        if raw_uid is not None:
            uid = raw_uid.decode() if isinstance(raw_uid, bytes) else str(raw_uid)
            user = await db.get(User, uid)

    if user is None and cid:
        stmt = select(User).where(User.papay_contract_id == cid).limit(1)
        user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        return True, "unknown_user_idempotent"

    if cid:
        user.papay_contract_id = cid[:64]
        user.auto_renew = True
        await db.flush()

    if out_code:
        await redis.delete(f"papay:occ:{out_code}")

    return True, "ok"
