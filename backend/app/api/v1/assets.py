"""图片 / 视频资源同源代理：MinIO「公网直链 URL」改写为 `{API_PUBLIC}/v1/assets/…`，

微信小程序真机只对 **已登记 HTTPS 域名** 放行 `<Image>` / `<Video>` 网络资源；MinIO 常挂载在 `/minio` 前缀下，
与 `downloadFile`/播放器策略组合后易出现 **黑屏 + 问号**（尤其 iOS）。
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from minio.error import S3Error
from starlette.responses import StreamingResponse

from app.integrations.minio import MinioStorageClient, get_minio_storage

router = APIRouter()

logger = logging.getLogger(__name__)

# 允许代理的图片 key 前缀：与写入 MinIO 时的命名约定一致
ALLOWED_IMAGE_PREFIXES: tuple[str, ...] = (
    "keyframes/",
    "thumbnails/",
    "share/wxa/",
    "samples/",
)

ALLOWED_VIDEO_PREFIXES: tuple[str, ...] = ("uploads/", "skeleton/", "samples/")

# 304 协商缓存的客户端缓存时间：1 天足够覆盖单次会话；图本身按 analysis_id 命名不会变
_IMAGE_CACHE_CONTROL = "public, max-age=86400, immutable"
# MP4（原片 / skeleton）分析完成后一般不覆盖；短时缓存兼顾迭代期覆盖发布
_VIDEO_CACHE_CONTROL = "public, max-age=86400"


def _traversal_segments(key: str) -> bool:
    return ".." in key.split("/")


def _parse_single_range(spec: str, size: int) -> tuple[int, int]:
    """解析形如 `234-567`、`234-`、`-567`（末尾 N 字节）的段，返回闭合区间 [start, end] inclusive."""
    if size <= 0:
        raise ValueError()
    m = re.fullmatch(r"(\d*)-(\d*)", spec.strip())
    if not m:
        raise ValueError()
    a, b = m.group(1), m.group(2)
    if a == "" and b == "":
        raise ValueError()
    try:
        if a == "" and b != "":
            suffix_len = int(b)
            if suffix_len <= 0:
                raise ValueError()
            start = max(0, size - suffix_len)
            end = size - 1
        elif a != "" and b == "":
            start = int(a)
            end = size - 1
        else:
            start, end = int(a), int(b)
    except ValueError as e:
        raise ValueError from e

    end = min(end, size - 1)
    if start < 0 or start > end or start >= size:
        raise ValueError()
    return start, end


@router.get("/assets/image/{key:path}")
def proxy_image(
    key: str,
    storage: MinioStorageClient = Depends(get_minio_storage),
) -> Response:
    """从 MinIO 内部端点返回图片字节流（同源代理）。"""
    if not any(key.startswith(p) for p in ALLOWED_IMAGE_PREFIXES):
        raise HTTPException(status_code=404, detail="not_found")
    if _traversal_segments(key):
        raise HTTPException(status_code=404, detail="not_found")

    try:
        resp = storage._internal.get_object(storage.bucket, key)
    except S3Error as e:
        if e.code in {"NoSuchKey", "NoSuchBucket"} or "404" in str(e):
            raise HTTPException(status_code=404, detail="not_found") from None
        logger.exception("proxy_image: minio fetch failed key=%s", key)
        raise HTTPException(status_code=502, detail="upstream_error") from e

    try:
        data = resp.read()
        content_type = resp.headers.get("Content-Type") or "image/jpeg"
    finally:
        resp.close()
        resp.release_conn()

    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": _IMAGE_CACHE_CONTROL},
    )


@router.api_route("/assets/video/{key:path}", methods=["GET", "HEAD"])
def proxy_video(
    request: Request,
    key: str,
    storage: MinioStorageClient = Depends(get_minio_storage),
):
    """流式输出 MP4，支持单个 `bytes=` Range（满足小程序播放器 seek）。"""
    if not any(key.startswith(p) for p in ALLOWED_VIDEO_PREFIXES):
        raise HTTPException(status_code=404, detail="not_found")
    if _traversal_segments(key):
        raise HTTPException(status_code=404, detail="not_found")

    try:
        stat = storage._internal.stat_object(storage.bucket, key)
    except S3Error as e:
        if e.code in {"NoSuchKey", "NoSuchBucket"} or "404" in str(e):
            raise HTTPException(status_code=404, detail="not_found") from None
        logger.exception("proxy_video: minio stat failed key=%s", key)
        raise HTTPException(status_code=502, detail="upstream_error") from e

    size = stat.size
    ctype = stat.content_type or "video/mp4"
    rng_bounds: tuple[int, int] | None = None
    raw_rng = request.headers.get("range")
    if request.method == "GET" and raw_rng and raw_rng.strip():
        stripped = raw_rng.strip()
        if not stripped.lower().startswith("bytes="):
            return Response(
                status_code=416,
                headers={"Content-Range": f"bytes */{size}"},
            )
        try:
            first = stripped[6:].split(",", 1)[0].strip()
            rng_bounds = _parse_single_range(first, size)
        except ValueError:
            return Response(
                status_code=416,
                headers={"Content-Range": f"bytes */{size}"},
            )

    headers: dict[str, str] = {
        "Accept-Ranges": "bytes",
        "Cache-Control": _VIDEO_CACHE_CONTROL,
    }

    def full_body_iter():
        resp = storage._internal.get_object(storage.bucket, key)
        try:
            chunk_size = 256 * 1024
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            resp.close()
            resp.release_conn()

    if rng_bounds is None:
        headers["Content-Length"] = str(size)
        if request.method == "HEAD":
            return Response(status_code=200, headers=headers, media_type=ctype)
        return StreamingResponse(
            full_body_iter(),
            media_type=ctype,
            headers=headers,
        )

    start, end = rng_bounds
    slice_len = end - start + 1
    headers["Content-Length"] = str(slice_len)
    headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    def range_iter():
        resp = storage._internal.get_object(
            storage.bucket, key, offset=start, length=slice_len,
        )
        try:
            chunk_size = 256 * 1024
            remaining = slice_len
            while remaining > 0:
                read_n = min(chunk_size, remaining)
                chunk = resp.read(read_n)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
        finally:
            resp.close()
            resp.release_conn()

    if request.method == "HEAD":
        return Response(status_code=206, headers=headers, media_type=ctype)
    return StreamingResponse(
        range_iter(),
        status_code=206,
        media_type=ctype,
        headers=headers,
    )
