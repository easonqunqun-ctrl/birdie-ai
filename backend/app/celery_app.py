"""Celery 应用实例（挥杆分析异步处理器）.

设计要点：
- Broker / result backend 都走 Redis：为避免与业务 cache 混住，挪到 DB 1（broker）
  和 DB 2（result），业务 cache 继续用 DB 0。
- `include` 列表里写死 `app.tasks.analysis_tasks`，worker 启动时自动 import，
  task 注册表就位；`-A app.celery_app` 入口即可。
- `task_always_eager`：默认 False（生产/集成）；测试里不开 eager，而是通过
  monkeypatch `app.services.analysis_service._dispatch_analysis_task` 直接调
  async 内核函数（更可控、不依赖 celery runtime）。
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from celery import Celery
from celery.schedules import crontab

from app.config import settings
from app.core.sentry import setup_sentry

# Sentry 初始化要在 ``Celery(...)`` 实例创建之前（CeleryIntegration 通过 signals
# 织入 ``task_prerun`` / ``task_failure`` 钩子，越早越可靠）。
# DSN 为空时 no-op；不会影响本地开发 / pytest（不连 broker 的纯测试也安全）。
setup_sentry()


def _with_db(url: str, db: int) -> str:
    """把 redis URL 的 DB 号替换成指定 DB（保留 auth/host/port 原样）."""
    parsed = urlparse(url)
    path = f"/{db}"
    return urlunparse(parsed._replace(path=path))


celery_app = Celery(
    "xiaoniao",
    broker=_with_db(settings.redis_url, 1),
    backend=_with_db(settings.redis_url, 2),
    include=[
        "app.tasks.analysis_tasks",
        "app.tasks.payment_tasks",
        "app.tasks.account_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # 单条分析任务上限 5 分钟；超过强制 kill（mock 模式下远不会触达）
    task_time_limit=300,
    task_soft_time_limit=270,
    # 启动时 broker 未就绪不应立刻崩溃（docker compose 启动序列偶发）
    broker_connection_retry_on_startup=True,
    # worker 预取 1 条：任务相对重（视频分析），避免一 worker 积压多条长任务
    worker_prefetch_multiplier=1,
    beat_schedule={
        # 需在部署栈中常驻 `celery -A app.celery_app beat` 才会触发
        "expire-stale-payment-orders": {
            "task": "xiaoniao.expire_stale_pending_orders",
            "schedule": crontab(minute="*/15"),
        },
        "membership-pre-expiry-notify": {
            "task": "xiaoniao.membership_pre_expiry_notify",
            "schedule": crontab(hour=0, minute=12),
        },
        # MVP §3.4 账号注销冷静期硬删兜底：用户即便不再登录也按时清理（PIPL）
        "purge-due-account-deletions": {
            "task": "xiaoniao.purge_due_account_deletions",
            "schedule": crontab(minute=17),  # 每小时第 17 分
        },
    },
)


__all__ = ["celery_app"]
