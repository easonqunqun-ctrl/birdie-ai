"""W6-T3：AI Engine 侧的轻量 MinIO/S3 客户端。

设计与 backend `app/integrations/minio.py` 对齐的两点重要约定：
- **internal vs public endpoint**：上传走容器内网 `MINIO_ENDPOINT`；返回给客户端
  的访问 URL 用 `MINIO_PUBLIC_ENDPOINT`，否则微信小程序 / 浏览器无法解析
  `http://minio:9000` 这种 docker 内域名
- **bucket 复用**：默认与 backend 用同一个 `MINIO_BUCKET`，按 key prefix 分目录
  （`skeleton/<id>.mp4` / `keyframes/<id>/...` / `skeleton_data/<id>.parquet`）

ai_engine 这边职责更窄：只需要 `put_file` + `build_public_url`。**没有**预签名上传
（那是 backend 的职责，给 client 直传用），也**没有** head/list（清理由 backend
定时任务做）。

容错策略
--------
- 当 `AI_ENGINE_DERIVED_ASSETS_ENABLED=false` 时，`put_file` 返回 `None`，调用方
  退化到占位 URL，不阻断主分析流程
- 上传失败（网络抖、bucket 不存在、磁盘满）log 一条 warning 并返回 `None`；
  上层把对应的 `*_url` 字段设为 `None`，前端用 fallback 兜底
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.config import settings

log = logging.getLogger("ai_engine.storage")


def _strip_scheme(endpoint: str) -> tuple[str, bool]:
    """从完整 URL 中分离 host[:port] + secure 标志（minio SDK 不接受 scheme）。"""
    parsed = urlparse(endpoint)
    if not parsed.netloc:
        return endpoint, False
    return parsed.netloc, parsed.scheme == "https"


class DerivedAssetsStorage:
    """衍生产物上传 + URL 构造。

    线程安全：minio-py 内部用 urllib3 PoolManager，自带连接池；
    ai_engine 这种 worker 模型可以直接共享单例。

    Attributes:
        enabled: false 时所有 put_file 返回 None；调用方 fallback
        bucket: 上传目标 bucket
    """

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        internal_endpoint: str | None = None,
        public_endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        region: str | None = None,
    ) -> None:
        self.enabled = settings.AI_ENGINE_DERIVED_ASSETS_ENABLED if enabled is None else enabled
        self._public_endpoint = (public_endpoint or settings.MINIO_PUBLIC_ENDPOINT).rstrip("/")
        self.bucket = bucket or settings.MINIO_BUCKET
        self.region = region or settings.MINIO_REGION

        if not self.enabled:
            log.warning("derived_assets_disabled")
            self._client: Minio | None = None
            return

        host, secure = _strip_scheme(internal_endpoint or settings.MINIO_ENDPOINT)
        self._client = Minio(
            host,
            access_key=access_key or settings.MINIO_ACCESS_KEY,
            secret_key=secret_key or settings.MINIO_SECRET_KEY,
            secure=secure,
            region=self.region,
        )

    # -------------------- 对外 API --------------------

    def put_file(
        self,
        local_path: Path | str,
        object_key: str,
        *,
        content_type: str = "application/octet-stream",
    ) -> str | None:
        """上传本地文件到 `<bucket>/<object_key>`，成功返回公网可访问 URL。

        Args:
            local_path: 本地文件绝对路径，必须存在且非零字节
            object_key: 对象 key（建议 `<prefix>/<analysis_id>/...`）
            content_type: MIME，影响浏览器/微信对响应的处理

        Returns:
            URL 字符串；上传失败 / disabled / 空文件 → None
        """
        if not self.enabled or self._client is None:
            return None

        local_path = Path(local_path)
        if not local_path.exists() or local_path.stat().st_size == 0:
            log.warning("upload_skipped_empty_file", extra={"path": str(local_path)})
            return None

        try:
            self._client.fput_object(
                self.bucket,
                object_key,
                str(local_path),
                content_type=content_type,
            )
        except S3Error as exc:
            log.warning(
                "minio_upload_failed",
                extra={
                    "bucket": self.bucket,
                    "object_key": object_key,
                    "code": exc.code,
                    "error": str(exc),
                },
            )
            return None
        except Exception as exc:  # pragma: no cover - 网络/其他异常
            log.warning(
                "minio_upload_unknown_error",
                extra={"bucket": self.bucket, "object_key": object_key, "error": str(exc)},
            )
            return None

        url = self.build_public_url(object_key)
        log.info(
            "minio_upload_ok",
            extra={
                "bucket": self.bucket,
                "object_key": object_key,
                "size": local_path.stat().st_size,
            },
        )
        return url

    def build_public_url(self, object_key: str) -> str:
        """构造公网 URL（bucket 已配 public download policy，不签名）。

        与 backend `MinioStorageClient.get_object_url` 行为一致。
        """
        return f"{self._public_endpoint}/{self.bucket}/{object_key}"

    def delete_object(self, object_key: str) -> bool:
        """删除对象；失败只打日志，不抛错（用于骨骼完成后清 normalized 临时片）。"""
        if not self.enabled or self._client is None or not object_key:
            return False
        try:
            self._client.remove_object(self.bucket, object_key)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "minio_delete_failed",
                extra={"bucket": self.bucket, "object_key": object_key, "error": str(exc)},
            )
            return False
        log.info(
            "minio_delete_ok",
            extra={"bucket": self.bucket, "object_key": object_key},
        )
        return True


# -------------------- 单例（避免每次分析都重建连接池） --------------------


@lru_cache(maxsize=1)
def get_storage() -> DerivedAssetsStorage:
    return DerivedAssetsStorage()


def reset_storage_for_tests() -> None:
    """测试用：清单例缓存，让下次 get_storage() 重新读 settings。"""
    get_storage.cache_clear()
