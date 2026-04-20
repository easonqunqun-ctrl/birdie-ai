"""Redis 客户端封装."""

from redis.asyncio import Redis, from_url

from app.config import settings

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """获取 Redis 客户端单例."""
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def close_redis() -> None:
    """应用关闭时清理 Redis 连接."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
