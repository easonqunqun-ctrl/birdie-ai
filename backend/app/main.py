"""FastAPI 应用入口."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.config import settings
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestContextMiddleware, register_exception_handlers
from app.core.production_guard import startup_production_guards
from app.core.redis import close_redis, get_redis
from app.core.wechat_deploy_hints import log_wechat_miniprogram_domain_hints

setup_logging()
logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭钩子."""
    logger.info(
        "app_starting",
        env=settings.APP_ENV,
        version=__version__,
        debug=settings.APP_DEBUG,
    )
    # 预热 Redis 连接
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("redis_connected")
    except Exception as e:
        logger.warning("redis_connect_failed", error=str(e))

    startup_production_guards(logger, settings)
    log_wechat_miniprogram_domain_hints(logger, settings)

    yield

    logger.info("app_stopping")
    await close_redis()


app = FastAPI(
    title="领翼golf · API",
    description="中国首款 AI 高尔夫智能教练 - 后端 API",
    version=__version__,
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_prod else None,
    redoc_url="/redoc" if not settings.is_prod else None,
    openapi_url="/openapi.json" if not settings.is_prod else None,
)

# 中间件（顺序：先注册的后执行）
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# 异常处理
register_exception_handlers(app)

# 路由
app.include_router(api_router, prefix="/v1")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "xiaoniao-ai-backend",
        "version": __version__,
        "env": settings.APP_ENV,
        "docs": "/docs",
    }
