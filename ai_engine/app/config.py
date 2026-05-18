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

    # 与仓库根 `.env.example` 一致：默认走真实 MediaPipe；仅本地想跳推理时显式设 true
    AI_ENGINE_MOCK_MODE: bool = False
    AI_ENGINE_PORT: int = 9000

    # 模型路径（真实模式才用到）
    POSE_MODEL_PATH: str = "app/models/pose_landmarker.task"

    # ==================== W6-T3：MinIO / S3 对象存储 ====================
    # 复用 backend 的 bucket（同一套 .env.local，键名一致）。三类衍生产物统一
    # 落到这个 bucket，路径前缀按"产物种类 / analysis_id"分目录便于清理。
    #
    # `MINIO_PUBLIC_ENDPOINT` 是签名/访问 URL 用的对外地址；ai_engine 容器内自己
    # 上传走 `MINIO_ENDPOINT`（容器网内网）。两者通常分别为 `http://localhost:9000`
    # 和 `http://minio:9000`。
    #
    # `AI_ENGINE_DERIVED_ASSETS_ENABLED` = false 时跳过上传（CI / 离线测试 / MinIO
    # 不可用时），real_pipeline 退化到占位 URL，不阻断分析主流程。
    MINIO_ENDPOINT: str = "http://minio:9000"
    MINIO_PUBLIC_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "xiaoniao-videos"
    MINIO_REGION: str = "us-east-1"
    AI_ENGINE_DERIVED_ASSETS_ENABLED: bool = True

    # 衍生产物的对象 key 前缀；改这里需要同步 docs/14
    DERIVED_SKELETON_PREFIX: str = "skeleton"
    DERIVED_KEYFRAME_PREFIX: str = "keyframes"
    DERIVED_POSE_DATA_PREFIX: str = "skeleton_data"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
