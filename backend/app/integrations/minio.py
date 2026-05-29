"""MinIO / S3 兼容对象存储客户端封装。

设计目标：
- 对业务层暴露 **3 个方法**：`presign_post_policy` / `head_object` / `get_object_url`。
- 后端容器访问 MinIO 走 `MINIO_ENDPOINT`（内网，如 `http://minio:9000`）；
  签发给小程序/浏览器的 POST 基准地址取自 `effective_minio_public_endpoint`
  （通常为 `MINIO_PUBLIC_ENDPOINT`；staging/prod 且仍为 localhost 占位时回落至
  `{API_PUBLIC_BASE_URL}/minio`，与 nginx 反代及微信合法域名对齐），
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
        self._public_endpoint = public_endpoint or settings.effective_minio_public_endpoint
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

    def put_object_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        """服务端上传对象（微信小程序经 `/v1/analyses/uploads/...` 兜底写入 MinIO/COS）."""
        from io import BytesIO

        bio = BytesIO(data)
        self._internal.put_object(
            self.bucket,
            key,
            bio,
            length=len(data),
            content_type=content_type,
        )

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

    def presign_get_url(
        self, key: str, *, expires_in_seconds: int = 3600
    ) -> tuple[str, datetime]:
        """签发 GET 预签名 URL（PDF 等私有对象临时下载）."""
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
        url = self._public.presigned_get_object(
            self.bucket,
            key,
            expires=timedelta(seconds=expires_in_seconds),
        )
        return url, expires_at


# -------------------- FastAPI 依赖注入入口 --------------------
_default_client: MinioStorageClient | None = None


def get_minio_storage() -> MinioStorageClient:
    """FastAPI `Depends` 用。测试中通过 `app.dependency_overrides` 替换为 fake 实现.

    `STORAGE_PROVIDER=cos` 时走腾讯云 COS 的 S3 兼容端点（`cos.<region>.myqcloud.com`）。"""
    global _default_client
    if _default_client is None:
        from app.config import settings

        if settings.STORAGE_PROVIDER == "cos":
            if not (settings.COS_SECRET_ID and settings.COS_SECRET_KEY and settings.COS_BUCKET):
                raise RuntimeError("COS_SECRET_ID / COS_SECRET_KEY / COS_BUCKET 未配置")
            # 与 S3 path-style 一致：endpoint 不含 bucket 名，签名 URL 形如
            # `https://cos.<region>.myqcloud.com/<bucket>`（见 `presign_post_policy` 内 `url` 拼接）
            internal = f"https://cos.{settings.COS_REGION}.myqcloud.com"
            public = (settings.COS_PUBLIC_BASE or "").rstrip() or internal
            _default_client = MinioStorageClient(
                internal_endpoint=internal,
                public_endpoint=public,
                access_key=settings.COS_SECRET_ID,
                secret_key=settings.COS_SECRET_KEY,
                bucket=settings.COS_BUCKET,
                region=settings.COS_REGION,
            )
        else:
            _default_client = MinioStorageClient()
    return _default_client


def reset_minio_storage() -> None:
    """仅测试/热重载用：清空单例缓存。"""
    global _default_client
    _default_client = None
