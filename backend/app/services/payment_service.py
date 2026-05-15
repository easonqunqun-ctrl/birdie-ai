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

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AppException, BadRequestError, ConflictError, NotFoundError, ThirdPartyError
from app.core.security import new_id
from app.integrations import wechat_pay_v3
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


# ==================== 下单 ====================
async def create_order(db: AsyncSession, user: User, plan_type: str) -> tuple[Order, PrepayParams]:
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
        prepay = PrepayParams(mock=True)
    else:
        prepay = await _create_wechat_prepay(db, order, user)

    return order, prepay


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
        return ctx.build_miniprogram_prepay(prepay_id)
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

    try:
        ctx = wechat_pay_v3.get_wechat_pay_v3()
    except (RuntimeError, ValueError, OSError) as e:
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
