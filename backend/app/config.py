"""应用配置：从环境变量加载，使用 pydantic-settings 校验."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """统一配置入口."""

    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ==================== 应用 ====================
    APP_ENV: Literal["local", "dev", "staging", "prod"] = "local"
    APP_DEBUG: bool = True
    APP_NAME: str = "xiaoniao-ai"
    APP_SECRET_KEY: str = "change-me"
    APP_LOG_LEVEL: str = "INFO"

    # ==================== 后端服务 ====================
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    BACKEND_WORKERS: int = 1
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:10086"

    # ==================== JWT ====================
    JWT_SECRET_KEY: str = "change-me-jwt"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_DAYS: int = 7

    # ==================== PostgreSQL ====================
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "xiaoniao"
    POSTGRES_PASSWORD: str = "xiaoniao_dev_password"
    POSTGRES_DB: str = "xiaoniao"
    DATABASE_URL: str = ""
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ==================== Redis ====================
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_URL: str = ""

    # ==================== 对象存储 ====================
    STORAGE_PROVIDER: Literal["minio", "cos"] = "minio"
    MINIO_ENDPOINT: str = "http://minio:9000"
    MINIO_PUBLIC_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "xiaoniao-videos"
    MINIO_REGION: str = "us-east-1"

    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_REGION: str = "ap-shanghai"
    COS_BUCKET: str = ""

    # ==================== 微信小程序 ====================
    WECHAT_MINIPROGRAM_APPID: str = "wx_placeholder_appid"
    WECHAT_MINIPROGRAM_SECRET: str = "placeholder_secret"
    WECHAT_MOCK_LOGIN: bool = True

    # ==================== 微信开放平台（App） ====================
    WECHAT_OPEN_APPID: str = ""
    WECHAT_OPEN_SECRET: str = ""

    # ==================== 微信支付 ====================
    # W7-T1：MVP 阶段默认 mock 模式。真实上线需：
    #   1. 商户号（需 ICP 备案）+ 商户证书
    #   2. `WECHAT_PAY_NOTIFY_URL` 指向公网可达回调地址 + 签名校验
    #   3. 把 `WECHAT_PAY_MOCK_MODE` 切回 False，启用 `services/payment_service.py`
    #      的真实分支（目前为 NotImplementedError）
    WECHAT_PAY_MOCK_MODE: bool = True
    WECHAT_PAY_MCH_ID: str = ""
    WECHAT_PAY_API_KEY: str = ""
    WECHAT_PAY_CERT_PATH: str = ""
    WECHAT_PAY_NOTIFY_URL: str = ""

    # ==================== 苹果内购 ====================
    APPLE_BUNDLE_ID: str = "com.xiaoniaoai.app"
    APPLE_SHARED_SECRET: str = ""
    APPLE_VERIFY_RECEIPT_URL: str = "https://sandbox.itunes.apple.com/verifyReceipt"

    # ==================== LLM ====================
    LLM_PROVIDER: Literal["deepseek", "qwen", "glm", "openai"] = "deepseek"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_MOCK_MODE: bool = False  # True 强制 FakeLLM；False 且 API_KEY 为空时也自动回退 Fake

    # ==================== AI Engine ====================
    AI_ENGINE_URL: str = "http://ai_engine:9000"
    # W6-T4：从 120s 降到 60s。docs/01 §4.2 用户最大容忍 120s（含网络回程 / Celery 调度
    # 排队），ai_engine 真实引擎 CPU 预算 30s（preprocess 5 + pose 12 + 其它 13），
    # 留 2x buffer = 60s。降下来可以更快感知到挂死任务，触发 _mark_failed + 退配额。
    AI_ENGINE_TIMEOUT: int = 60
    # backend 不直接消费这个变量（只在 ai_engine 容器内决定走 mock or real），
    # 留在这里仅为 .env.local 校验完整性 + 便于将来 backend 侧加 fallback 逻辑
    AI_ENGINE_MOCK_MODE: bool = False

    # ==================== 业务规则 ====================
    FREE_USER_MONTHLY_ANALYSES: int = 3
    FREE_USER_DAILY_CHATS: int = 5
    MAX_VIDEO_DURATION_SECONDS: int = 30
    MIN_VIDEO_DURATION_SECONDS: int = 3
    MAX_VIDEO_SIZE_BYTES: int = 100 * 1024 * 1024  # 100MB

    @property
    def database_url(self) -> str:
        """优先使用显式 DATABASE_URL，否则按字段组装."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        """同步版连接串，给 Alembic 用."""
        url = self.database_url
        return url.replace("+asyncpg", "+psycopg2") if "+asyncpg" in url else url

    @property
    def redis_url(self) -> str:
        """组装 Redis URL."""
        if self.REDIS_URL:
            return self.REDIS_URL
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS origins 解析为列表."""
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_local(self) -> bool:
        return self.APP_ENV == "local"

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例配置."""
    return Settings()


settings = get_settings()
