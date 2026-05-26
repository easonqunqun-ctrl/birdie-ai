"""M7-14 引擎版本路由 + AB 灰度.

设计要点
--------
- **请求级灰度**：同一 ai_engine 容器内可按 ``user_id`` 哈希分桶，5% / 25% / 50% / 100%
  四档常用；同一 user_id 在 ``rollout_pct`` 不变期内永远落同一桶。
- **配置来源优先级**：``Redis (60s TTL)`` > ``env M7_V2_ROLLOUT_PCT`` > 0。
  Redis 不可用时静默回落（不阻塞推理），日志 WARN 一次。
- **mock 模式短路**：``AI_ENGINE_MOCK_MODE=true`` 时永远返回 ``v1`` 走 mock 管线，
  与 §3.5 一致。
- **降级保护**：``set_rollout_pct(new_pct)`` 当 ``new_pct < previous_pct`` 时拒绝，
  需要调用方显式传 ``force=True`` 才生效（防止误操作把已经在 V2 的用户回退）。

监控
----
后续可在 main.analyze 路由里读取 ``get_engine_version()`` 的返回值打到 structlog，
配 Prometheus rule（kickoff §3.7）即可监控失败率。
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from typing import Literal

import structlog

log = structlog.get_logger("version_router")

EngineVersion = Literal["v1", "v2"]

ENGINE_V1: EngineVersion = "v1"
ENGINE_V2: EngineVersion = "v2"

# Redis 缓存 TTL（秒）；docs §3.4
ROLLOUT_PCT_CACHE_TTL = 60
ROLLOUT_REDIS_KEY = "m7:v2:rollout_pct"

# 进程级 fallback 缓存（避免每次 analyze 都打 Redis）
_pct_cache_lock = threading.Lock()
_pct_cache: dict[str, float | int] = {"value": 0, "expires_at": 0.0}


def _user_bucket(user_id: str) -> int:
    """``user_id`` → ``[0, 100)`` 整数桶。

    md5 hash 取后 32 bit % 100，**纯函数**，同输入同输出，单测易写。
    """

    h = hashlib.md5(user_id.encode("utf-8")).hexdigest()  # noqa: S324 (非密码学用途)
    return int(h[-8:], 16) % 100


def _env_pct() -> int:
    raw = os.environ.get("M7_V2_ROLLOUT_PCT", "0")
    try:
        pct = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, pct))


def _redis_pct() -> int | None:
    """尝试从 Redis 读 rollout pct，失败时返回 None。

    Redis 不在 ai_engine 容器的硬依赖里（一期不用 Redis），失败容忍：
    redis 包未装 / 网络不通 / key 不存在 → 全部 None 走 env fallback。
    """

    try:
        import redis  # type: ignore[import-not-found]
    except ImportError:
        return None

    redis_url = os.environ.get("REDIS_URL") or os.environ.get("M7_V2_REDIS_URL")
    if not redis_url:
        return None
    try:
        client = redis.from_url(redis_url, socket_timeout=1, socket_connect_timeout=1)
        raw = client.get(ROLLOUT_REDIS_KEY)
    except Exception as exc:  # noqa: BLE001
        log.warning("rollout_pct_redis_unreachable", err=repr(exc))
        return None
    if raw is None:
        return None
    try:
        pct = int(raw)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, pct))


def get_rollout_pct(*, force_refresh: bool = False) -> int:
    """返回当前 ``M7_V2_ROLLOUT_PCT``，60s 进程级缓存."""

    now = time.time()
    with _pct_cache_lock:
        if not force_refresh and now < _pct_cache["expires_at"]:
            return int(_pct_cache["value"])

    pct = _redis_pct()
    if pct is None:
        pct = _env_pct()

    with _pct_cache_lock:
        _pct_cache["value"] = pct
        _pct_cache["expires_at"] = now + ROLLOUT_PCT_CACHE_TTL
    return int(pct)


def invalidate_cache() -> None:
    """单测 / admin endpoint 即时调用一次即可读到最新 pct."""

    with _pct_cache_lock:
        _pct_cache["expires_at"] = 0.0


def get_engine_version(user_id: str | None) -> EngineVersion:
    """根据 ``user_id`` + 当前 rollout pct 决定走哪一版 pipeline.

    - ``user_id`` 为 None / 空：保守走 ``v1``（无法分桶）
    - ``AI_ENGINE_MOCK_MODE=true`` 时仍返回 ``v1``，由路由层决定走 mock
      （详 main.analyze 路由）
    """

    if not user_id:
        return ENGINE_V1
    pct = get_rollout_pct()
    if pct <= 0:
        return ENGINE_V1
    if pct >= 100:
        return ENGINE_V2
    if _user_bucket(user_id) < pct:
        return ENGINE_V2
    return ENGINE_V1


class RolloutDowngradeRequiresForce(Exception):
    """``new_pct < previous_pct`` 时拒绝降级，需 ``force=True``."""


def set_rollout_pct(new_pct: int, *, force: bool = False) -> dict:
    """运维 / admin endpoint 主动设置 pct 到 Redis（如未配 Redis 仅刷进程缓存）.

    返回 ``{previous_pct, current_pct, requires_confirm}``，admin API 透传。
    """

    new_pct = max(0, min(100, int(new_pct)))
    prev = get_rollout_pct(force_refresh=True)

    if new_pct < prev and not force:
        raise RolloutDowngradeRequiresForce(
            f"pct {prev} -> {new_pct} 为降级，需 force=True 再调一次确认"
        )

    redis_url = os.environ.get("REDIS_URL") or os.environ.get("M7_V2_REDIS_URL")
    if redis_url:
        try:
            import redis  # type: ignore[import-not-found]

            client = redis.from_url(
                redis_url, socket_timeout=1, socket_connect_timeout=1
            )
            client.set(ROLLOUT_REDIS_KEY, str(new_pct))
        except Exception as exc:  # noqa: BLE001
            log.warning("rollout_pct_redis_set_failed", err=repr(exc))

    invalidate_cache()
    log.info(
        "rollout_pct_changed",
        previous_pct=prev,
        current_pct=new_pct,
        force=force,
    )
    return {
        "previous_pct": prev,
        "current_pct": new_pct,
        "downgrade": new_pct < prev,
    }


__all__ = [
    "ENGINE_V1",
    "ENGINE_V2",
    "EngineVersion",
    "ROLLOUT_REDIS_KEY",
    "RolloutDowngradeRequiresForce",
    "_user_bucket",  # 单测可见
    "get_engine_version",
    "get_rollout_pct",
    "invalidate_cache",
    "set_rollout_pct",
]
