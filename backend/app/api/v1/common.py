"""通用接口：健康检查、埋点上报."""

from datetime import UTC, datetime

from fastapi import APIRouter

from app import __version__
from app.config import settings
from app.core.database import engine
from app.core.redis import get_redis

router = APIRouter()


@router.get("/health", summary="健康检查")
async def health_check():
    """检查后端、数据库、Redis 是否就绪."""
    services = {"backend": "ok", "database": "unknown", "redis": "unknown"}

    # DB
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        services["database"] = "ok"
    except Exception as e:
        services["database"] = f"error: {e}"

    # Redis
    try:
        redis = await get_redis()
        await redis.ping()
        services["redis"] = "ok"
    except Exception as e:
        services["redis"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return {
        "status": overall,
        "version": __version__,
        "env": settings.APP_ENV,
        "timestamp": datetime.now(UTC).isoformat(),
        "services": services,
    }
