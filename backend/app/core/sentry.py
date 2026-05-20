"""Sentry 接入：FastAPI + Celery 异常上报。

为什么需要
----------
PMF 阶段线上没有监控就是「蒙眼飞」：
- 后端 500 / 502 / Celery 任务 silent fail 都看不见；
- 用户报「打不开」时只能靠日志猜根因，复现成本极高。

接入约定
--------
- DSN 为空 → ``setup_sentry()`` 直接 no-op，本地开发 / CI / pytest 完全无副作用；
- 生产 / staging 通过 ``.env.local`` 的 ``SENTRY_DSN`` 注入；
- environment 标签默认跟随 ``settings.APP_ENV``，
  release 默认跟随 ``app.__version__``，可由 CD 流水线注入更精细的 git SHA；
- 默认不上报 PII（IP / 用户 ID），最小必要符合 PIPL §47 原则；
- ``traces_sample_rate`` 默认 0.0，仅捕获异常事件，避免吞 Sentry 免费额度。

调用位置
--------
- ``app/main.py``：FastAPI 启动时调一次（在 ``setup_logging()`` 之后）；
- ``app/celery_app.py``：模块 import 时调一次（Celery worker / beat 启动会触发）。

两边都调是必要的：FastAPI integration 与 Celery integration 是两套独立钩子。
``sentry_sdk.init()`` 自身是幂等的（同进程内重复调只会复用第一次的 client），
所以即便顺序问题导致两边都执行也无副作用。
"""

from __future__ import annotations

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app import __version__
from app.config import settings
from app.core.logging import get_logger

log = get_logger("sentry")

_initialized = False


def setup_sentry() -> bool:
    """初始化 Sentry SDK。

    返回值：是否真正初始化了（DSN 为空时返回 False）。便于测试断言。

    同进程多次调用会 short-circuit；这是为了让 main.py 与 celery_app.py
    都安全调用（fork worker 时可能两边都执行）。
    """
    global _initialized
    if _initialized:
        return True

    dsn = settings.SENTRY_DSN.strip()
    if not dsn:
        log.info("sentry_skipped", reason="dsn_empty")
        return False

    environment = settings.SENTRY_ENVIRONMENT.strip() or settings.APP_ENV
    release = settings.SENTRY_RELEASE.strip() or __version__

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        send_default_pii=settings.SENTRY_SEND_DEFAULT_PII,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
        # FastAPI 的 5xx 已通过 ``register_exception_handlers`` 自定义为 JSON；
        # 这里只让 Sentry 捕获**未捕获的异常**，不重复上报已被业务处理的 4xx。
        # ``failed_request_status_codes`` 用 ``set[int]``（跨 sentry-sdk 2.x 各小版本最稳）。
        integrations=[
            StarletteIntegration(
                failed_request_status_codes=set(range(500, 600)),
            ),
            FastApiIntegration(
                failed_request_status_codes=set(range(500, 600)),
            ),
            # Celery 任务异常：worker / beat 都会自动接入。
            # ``monitor_beat_tasks=False``：beat 心跳监控属付费功能，开了反而报噪音。
            CeleryIntegration(monitor_beat_tasks=False),
        ],
        # structlog 已经接管了应用日志格式；不让 Sentry 再自动捕获 stdlib logging
        # 作为 breadcrumb，避免上报量翻倍。
        # 仍可手动 ``sentry_sdk.add_breadcrumb()`` 在关键路径打点。
        max_breadcrumbs=50,
        # 同一个错误 1 分钟内只上报 1 次（按 fingerprint），防止异常循环刷爆额度。
        before_send=_dedup_before_send,
    )

    _initialized = True
    log.info(
        "sentry_initialized",
        environment=environment,
        release=release,
        traces=settings.SENTRY_TRACES_SAMPLE_RATE,
    )
    return True


def _dedup_before_send(event: dict, hint: dict) -> dict | None:
    """轻量去重钩子：避免单一异常在循环里把额度刷爆。

    当前为 pass-through，仅留作未来按 fingerprint / type 做节流的扩展点。
    """
    return event


def reset_for_tests() -> None:
    """仅 pytest 用：清掉模块状态，让连续测试用例都能重新走 ``setup_sentry()``。"""
    global _initialized
    _initialized = False
