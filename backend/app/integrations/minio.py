"""MinIO / S3 兼容对象存储客户端封装。

设计目标：
- 对业务层暴露 **3 个方法**：`presign_post_policy` / `head_object` / `get_object_url`。
- 后端容器访问 MinIO 走 `MINIO_ENDPOINT`（内网，如 `http://minio:9000`）；
  但签发给客户端的直传 URL 必须用 `MINIO_PUBLIC_ENDPOINT`（公网/宿主机，如 `http://localhost:9000`），
  因为客户端（微信小程序 / 浏览器）解析不了 Docker 内部域名。
  为此内部用两个 Minio 实例，签名时用 public 这个。
- T1 不依赖外部网络；单元测试通过依赖注入替换 `MinioStorageClient`。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from minio import Minio
from minio.datatypes import PostPolicy
from minio.error import S3Error

from app.config import settings


def _strip_scheme(endpoint: str) -> tuple[str, bool]:
    """从完整 URL 中分离出 host[:port] 与 secure 标志（minio SDK 的 endpoint 参数不含 scheme）."""
    parsed = urlparse(endpoint)
    if not parsed.netloc:
        # 未带 scheme：默认当作 http
        return endpoint, False
    return parsed.netloc, parsed.scheme == "https"


class MinioStorageClient:
    """包一层以方便在单元测试里 monkeypatch 或注入 Fake。"""

    def __init__(
        self,
        *,
        internal_endpoint: str | None = None,
        public_endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket: str | None = None,
        region: str | None = None,
    ) -> None:
        self._internal_endpoint = internal_endpoint or settings.MINIO_ENDPOINT
        self._public_endpoint = public_endpoint or settings.MINIO_PUBLIC_ENDPOINT
        self.bucket = bucket or settings.MINIO_BUCKET
        self.region = region or settings.MINIO_REGION
        ak = access_key or settings.MINIO_ACCESS_KEY
        sk = secret_key or settings.MINIO_SECRET_KEY

        internal_host, internal_secure = _strip_scheme(self._internal_endpoint)
        public_host, public_secure = _strip_scheme(self._public_endpoint)

        # 业务调用（head_object 等）走容器内网
        self._internal = Minio(
            internal_host,
            access_key=ak,
            secret_key=sk,
            secure=internal_secure,
            region=self.region,
        )
        # 签名发给客户端的 policy，URL 必须指向公网地址
        self._public = Minio(
            public_host,
            access_key=ak,
            secret_key=sk,
            secure=public_secure,
            region=self.region,
        )

    # -------------------- 对外 API --------------------
    def presign_post_policy(
        self,
        *,
        key: str,
        content_type: str,
        max_size: int,
        min_size: int = 1,
        expires_in_seconds: int = 3600,
    ) -> tuple[str, dict[str, str], datetime]:
        """签发一个 MinIO 预签名 POST policy。

        客户端拿到 `(url, fields, expires_at)` 后，需要：
        1. 以 `url` 为目标，做 multipart/form-data POST；
        2. 将 `fields` 里的所有键值作为 form 字段附带（policy / x-amz-* / key 等）；
        3. 最后一个字段名必须是 `file`，内容是视频二进制。

        `min_size=1` 防止空文件通过；`max_size` 由调用方按 100MB 上限传入。
        """
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
        policy = PostPolicy(self.bucket, expires_at)
        # 禁止客户端修改 key（只能上传到我们指定的路径）
        policy.add_equals_condition("key", key)
        # 禁止客户端修改 content-type（如果客户端传错，对象存储会拒绝）
        policy.add_equals_condition("Content-Type", content_type)
        # 文件大小范围约束：超出服务端直接拒绝
        policy.add_content_length_range_condition(min_size, max_size)

        form_fields = dict(self._public.presigned_post_policy(policy))
        # MinIO SDK 只回 policy / x-amz-* 这几个签名字段；`key` / `Content-Type`
        # 是 policy 的 equals 条件约束项，必须由客户端作为 form-data 一并提交，
        # 否则 S3 会以 "MalformedPOSTRequest: name of the uploaded key is missing" 拒绝。
        # 因此我们在这里显式补全到返回字段里，前端照搬一份即可。
        form_fields["key"] = key
        form_fields["Content-Type"] = content_type

        url = f"{self._public_endpoint.rstrip('/')}/{self.bucket}"
        return url, form_fields, expires_at

    def head_object(self, key: str) -> dict | None:
        """查对象元信息；不存在返回 None（其他错误抛出）。"""
        try:
            stat = self._internal.stat_object(self.bucket, key)
        except S3Error as e:
            # NoSuchKey 或 404：视为不存在
            if e.code in {"NoSuchKey", "NoSuchBucket"} or "404" in str(e):
                return None
            raise
        return {
            "size": stat.size,
            "etag": stat.etag,
            "content_type": stat.content_type,
            "last_modified": stat.last_modified,
        }

    def get_object_url(self, key: str) -> str:
        """构造公网可访问的下载 URL（bucket 已设置为 public download，无需签名）."""
        return f"{self._public_endpoint.rstrip('/')}/{self.bucket}/{key}"


# -------------------- FastAPI 依赖注入入口 --------------------
_default_client: MinioStorageClient | None = None


def get_minio_storage() -> MinioStorageClient:
    """FastAPI `Depends` 用。测试中通过 `app.dependency_overrides` 替换为 fake 实现。"""
    global _default_client
    if _default_client is None:
        _default_client = MinioStorageClient()
    return _default_client


def reset_minio_storage() -> None:
    """仅测试/热重载用：清空单例缓存。"""
    global _default_client
    _default_client = None
