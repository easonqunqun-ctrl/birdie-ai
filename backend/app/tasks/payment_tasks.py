"""与支付生命周期相关的 Celery 任务."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select

from app.celery_app import celery_app
from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis
from app.integrations.wechat_subscribe_message import send_membership_pre_expiry_notification
from app.models.user import User
from app.services import payment_service
from app.tasks.analysis_tasks import _run_coro_in_thread

log = structlog.get_logger("tasks.payment")


async def _expire_stale_pending_orders_async() -> int:
    async with AsyncSessionLocal() as db:
        n = await payment_service.expire_stale_pending_orders(db)
        await db.commit()
        return n


@celery_app.task(name="xiaoniao.expire_stale_pending_orders")
def expire_stale_pending_orders_task() -> int:
    """关闭超时未支付的订单（pending → cancelled）。由 Celery Beat 或小周期 cron 触发。"""
    n = _run_coro_in_thread(_expire_stale_pending_orders_async())
    log.info("expire_stale_pending_orders_done", count=n)
    return n


async def _membership_pre_expiry_notify_async() -> int:
    """会员「到期前 N 天」一次性订阅消息（上海日历与 `membership_expires_at` 对齐）。"""
    n_days = int(settings.MEMBERSHIP_PRE_EXPIRY_NOTIFY_DAYS or 0)
    if n_days <= 0:
        return 0
    if not settings.WECHAT_SUBSCRIBE_MESSAGE_ENABLED:
        return 0
    if not (settings.WECHAT_SUBSCRIBE_MEMBERSHIP_PRE_EXPIRE_TEMPLATE_ID or "").strip():
        return 0

    cn = ZoneInfo("Asia/Shanghai")
    now_utc = datetime.now(UTC)
    now_cn = now_utc.astimezone(cn)

    async with AsyncSessionLocal() as db:
        stmt = select(User).where(
            User.membership_type != "free",
            User.membership_expires_at.isnot(None),
            User.deleted_at.is_(None),
        )
        rows = list((await db.execute(stmt)).scalars().all())

    redis = await get_redis()
    sent = 0
    for u in rows:
        exp = u.membership_expires_at
        if exp is None:
            continue
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        exp_cn = exp.astimezone(cn)
        delta_days = (exp_cn.date() - now_cn.date()).days
        if delta_days != n_days:
            continue
        if not payment_service.is_member(u, now=now_utc):
            continue
        oid = u.wechat_openid
        if not oid or not str(oid).strip():
            continue
        rkey = f"sub:preexpiry:{u.id}:{exp_cn.date().isoformat()}"
        ok = await redis.set(rkey, "1", nx=True, ex=86400 * 45)
        if not ok:
            continue
        try:
            await send_membership_pre_expiry_notification(openid=oid, expires_at=exp)
            sent += 1
        except Exception as exc:
            log.warning("pre_expiry_notify_user_failed", user_id=u.id, error=str(exc))
    return sent


@celery_app.task(name="xiaoniao.membership_pre_expiry_notify")
def membership_pre_expiry_notify_task() -> int:
    n = _run_coro_in_thread(_membership_pre_expiry_notify_async())
    log.info("membership_pre_expiry_notify_done", count=n)
    return n
