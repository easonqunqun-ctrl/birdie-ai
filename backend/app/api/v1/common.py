"""通用接口：健康检查、埋点上报."""

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter

from app import __version__
from app.config import settings
from app.core.database import engine
from app.core.redis import get_redis

router = APIRouter()


@router.get("/health", summary="健康检查")
async def health_check():
    """检查后端、数据库、Redis、AI 引擎是否就绪（引擎单独探针便于发现误开 mock）."""
    services = {"backend": "ok", "database": "unknown", "redis": "unknown", "ai_engine": "unknown"}
    ai_engine_detail: dict[str, object] = {"reachable": False, "mock_mode": None}

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

    # AI Engine（短超时；与 backend 配置的 AI_ENGINE_URL 一致）
    base = settings.AI_ENGINE_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            r = await client.get(f"{base}/health")
        if r.status_code != 200:
            services["ai_engine"] = f"error: http {r.status_code}"
            ai_engine_detail["error"] = f"http {r.status_code}"
        else:
            payload = r.json()
            ai_engine_detail["reachable"] = True
            mock_mode = payload.get("mock_mode")
            ai_engine_detail["mock_mode"] = mock_mode
            strict_env = settings.APP_ENV in ("staging", "prod")
            if strict_env and mock_mode is True:
                ai_engine_detail["warning"] = (
                    "AI_ENGINE_MOCK_MODE=true on engine; skeleton/video derivation will not reflect real MediaPipe"
                )
                services["ai_engine"] = "degraded: mock_mode=true"
            else:
                services["ai_engine"] = "ok"
    except Exception as e:
        services["ai_engine"] = f"error: {e}"
        ai_engine_detail["error"] = str(e)

    overall = "ok" if all(v == "ok" for v in services.values()) else "degraded"
    return {
        "status": overall,
        "version": __version__,
        "env": settings.APP_ENV,
        "timestamp": datetime.now(UTC).isoformat(),
        "services": services,
        "ai_engine": ai_engine_detail,
    }
