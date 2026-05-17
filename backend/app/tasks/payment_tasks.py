"""与支付生命周期相关的 Celery 任务."""

from __future__ import annotations

import structlog

from app.celery_app import celery_app
from app.core.database import AsyncSessionLocal
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
