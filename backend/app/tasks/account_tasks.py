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


async def _purge_due_account_deletions_async() -> tuple[int, int]:
    """扫描所有冷静期已到期的 user 行并逐个调 ``purge_user_if_due``。

    返回 ``(purged_count, failed_count)``。出现任何单行异常 → 记 ``log.exception``
    保留 traceback 后跳过该行，不影响后续清理。
    """
    purged = 0
    failed = 0
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
            except Exception:  # pragma: no cover - 防御性兜底
                await db.rollback()
                failed += 1
                # log.exception 自动带 traceback；structlog 的 KV 仍然附在条目上
                log.exception("account_deletion_purge_failed", user_id=user.id)
    return purged, failed


# 任务时长 override：默认 worker 配置 task_time_limit=300s 是面向单条挥杆分析的；
# 本任务做 500 条用户 CASCADE 删除（含 swing_analyses / orders 等子表），在生产积压
# 历史时需要更宽的时长上限。soft=25min 给一次主动 cleanup 机会；hard=30min 上限。
@celery_app.task(
    name="xiaoniao.purge_due_account_deletions",
    time_limit=30 * 60,
    soft_time_limit=25 * 60,
)
def purge_due_account_deletions_task() -> dict[str, int]:
    """Celery 入口；按 ``celery_app.beat_schedule`` 每小时触发。"""
    purged, failed = _run_coro_in_thread(_purge_due_account_deletions_async())
    log.info("account_deletion_purge_done", purged=purged, failed=failed)
    return {"purged": purged, "failed": failed}
