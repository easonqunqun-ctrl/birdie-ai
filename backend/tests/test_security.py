"""W8-T5：/v1/security/media-check 集成测试。

覆盖点
------
1. mock 模式下上传一张"普通"图 → passed=True
2. mock 模式下文件名含 "violation" → passed=False + reason
3. 未登录（无 Authorization 头）→ 401
4. 图片过大（> 1MB）→ 413
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


def _png_bytes(size: int) -> bytes:
    """生成指定长度的 fake 二进制（内容不是真 PNG，但 API 接受任意字节）."""
    return b"\x89PNG\r\n\x1a\n" + b"0" * max(size - 8, 0)


@pytest.mark.asyncio
async def test_media_check_passes_for_normal_image(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    files = {"media": ("thumb.jpg", _png_bytes(1024), "image/jpeg")}
    resp = await client.post(
        "/v1/security/media-check",
        headers=auth_headers,
        files=files,
        data={"scene": "analysis"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["passed"] is True


@pytest.mark.asyncio
async def test_media_check_rejects_violation_image(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # mock 分支：文件名匹配 "violation" 会被当成违规
    files = {
        "media": ("violation_thumb.jpg", _png_bytes(1024), "image/jpeg"),
    }
    resp = await client.post(
        "/v1/security/media-check", headers=auth_headers, files=files
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["passed"] is False
    assert body["data"]["reason"]


@pytest.mark.asyncio
async def test_media_check_requires_auth(client: AsyncClient) -> None:
    files = {"media": ("thumb.jpg", _png_bytes(1024), "image/jpeg")}
    resp = await client.post("/v1/security/media-check", files=files)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_media_check_rejects_oversize(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # 1MB + 1 字节
    files = {
        "media": ("huge.jpg", _png_bytes(1024 * 1024 + 1), "image/jpeg"),
    }
    resp = await client.post(
        "/v1/security/media-check", headers=auth_headers, files=files
    )
    # FastAPI HTTPException(413) → 直接 413；没经过统一响应包装
    assert resp.status_code == 413
