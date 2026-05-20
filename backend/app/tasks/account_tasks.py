"""账号注销冷静期到期清理（MVP §3.4）。

设计要点
--------
- `get_user_by_id` 已经做了**惰性清理**（用户下次发请求时触发硬删）。
- 本任务是**兜底**：用户申请注销后若再也不登录，依然要在 ``account_deletion_scheduled_at``
  到期后按时清理；否则承诺与 PIPL 合规存在风险。
- 调度由 ``celery_app.beat_schedule`` 触发；每小时跑一次，单批最多 ``BATCH_SIZE`` 个用户，
  避免大量历史堆积时把 worker 长时间卡死。
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from app.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.services import account_deletion_service
from app.tasks.analysis_tasks import _run_coro_in_thread

log = structlog.get_logger("tasks.account")

# 单次 beat 调用最多清理多少账号：足够追赶上每小时新增的注销量；
# 历史堆积一次跑不完也无所谓——下次 beat 再继续。
BATCH_SIZE = 500


async def _purge_due_account_deletions_async() -> int:
    """扫描所有冷静期已到期的 user 行并逐个调 ``purge_user_if_due``。

    返回成功清理的数量。出现任何单行异常 → 记录日志后跳过该行，不影响后续清理。
    """
    purged = 0
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        stmt = (
            select(User)
            .where(
                User.account_deletion_scheduled_at.isnot(None),
                User.account_deletion_scheduled_at <= now,
                User.deleted_at.is_(None),
            )
            .limit(BATCH_SIZE)
        )
        rows = list((await db.execute(stmt)).scalars().all())

    for user in rows:
        # 每个用户独立 session：``purge_user_if_due`` 内部 commit + DELETE CASCADE
        # 可能比较重，放同一 session 容易拉长事务、放大锁面。
        async with AsyncSessionLocal() as db:
            fresh = await db.get(User, user.id)
            if fresh is None:
                continue
            try:
                if await account_deletion_service.purge_user_if_due(db, fresh):
                    purged += 1
            except Exception as exc:  # pragma: no cover - 防御性兜底
                await db.rollback()
                log.warning(
                    "account_deletion_purge_failed",
                    user_id=user.id,
                    error=str(exc),
                )
    return purged


@celery_app.task(name="xiaoniao.purge_due_account_deletions")
def purge_due_account_deletions_task() -> int:
    """Celery 入口；按 ``celery_app.beat_schedule`` 每小时触发。"""
    n = _run_coro_in_thread(_purge_due_account_deletions_async())
    log.info("account_deletion_purge_done", count=n)
    return n
