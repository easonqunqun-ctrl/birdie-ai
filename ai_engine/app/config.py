"""AI Engine 配置."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_ENV: str = "local"
    APP_DEBUG: bool = True
    APP_LOG_LEVEL: str = "INFO"

    AI_ENGINE_MOCK_MODE: bool = True
    AI_ENGINE_PORT: int = 9000

    # 模型路径（真实模式才用到）
    POSE_MODEL_PATH: str = "app/models/pose_landmarker.task"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# 容器外开发时的兜底
os.environ.setdefault("AI_ENGINE_MOCK_MODE", "true")
