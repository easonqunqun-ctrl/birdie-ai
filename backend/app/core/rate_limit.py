"""基于 Redis 的用户维度速率限制.

MVP 方案：**固定窗口计数器**
-------------------------
每个 (user_id, action) 一个 Redis key：`ratelimit:{action}:{user_id}:{window_start_epoch}`。
- `INCR` 拿到当前窗口内的计数
- 第一次命中时 `EXPIRE` 到窗口尾
- 超限则抛 `RateLimitError(40009)`

为什么不用滑动窗口？
- 滑动窗口（Sorted Set + ZADD/ZCOUNT）内存和运算开销都大
- MVP 每分钟 20 次对话，固定窗口的"边界抖动"（前 59s 用完 + 下个窗口再满）业务上
  可接受；真正要防刷时 W8 可以换成 `redis-cell` 令牌桶模块
- 固定窗口的实现只有 2 条 Redis 命令，网络往返成本低

用法：
    await check_rate_limit(redis, user_id="usr_xxx", action="chat.send", limit=20, window_sec=60)
    # 超限抛 RateLimitError
"""

from __future__ import annotations

import time

from redis.asyncio import Redis

from app.core.exceptions import RateLimitError

# 默认速率配置：对话发送 20/分钟
CHAT_SEND_LIMIT = 20
CHAT_SEND_WINDOW_SEC = 60


async def check_rate_limit(
    redis: Redis,
    *,
    user_id: str,
    action: str,
    limit: int,
    window_sec: int,
) -> int:
    """校验速率限制；命中上限抛 `RateLimitError(40009)`。

    返回当前窗口内该用户已发起的次数（含本次）；上层如果需要把"剩余次数"回显
    给客户端（X-RateLimit-Remaining 头），可以用 `limit - 返回值`。

    Redis key TTL 的设定：
    - 只在 key 从 0 → 1 时 EXPIRE（避免每次 INCR 都刷新 TTL 导致"永远不过期"）
    - window_sec + 1：防止极端情况下 TTL 比窗口短 1 秒造成边界误判
    """
    now = int(time.time())
    window_start = now - (now % window_sec)
    key = f"ratelimit:{action}:{user_id}:{window_start}"

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_sec + 1)

    if count > limit:
        raise RateLimitError(
            code=40009,
            message=f"操作过于频繁，每 {window_sec} 秒最多 {limit} 次",
        )
    return count


async def check_chat_send_rate(redis: Redis, user_id: str) -> int:
    """对话发送专用封装：20 次/分钟."""
    return await check_rate_limit(
        redis,
        user_id=user_id,
        action="chat.send",
        limit=CHAT_SEND_LIMIT,
        window_sec=CHAT_SEND_WINDOW_SEC,
    )
