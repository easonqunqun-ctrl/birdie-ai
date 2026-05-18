"""微信小程序码（无数量限制的 getwxacodeunlimited）."""

from __future__ import annotations

import json

import httpx

from app.integrations.wechat_access_token import get_access_token


async def fetch_wxacode_unlimited_png(*, scene: str, page: str, width: int = 430) -> bytes:
    """返回 PNG 二进制。`scene` 须 ≤32 可见字符。"""
    if len(scene) > 32:
        raise ValueError("getwxacodeunlimited: scene 最长 32 个可见字符")

    token = await get_access_token()
    if token == "mock_access_token":
        # 测试环境：最小 PNG 文件头占位（不作为有效图片展示）
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    url = "https://api.weixin.qq.com/wxa/getwxacodeunlimit"
    body = {"scene": scene, "page": page, "width": int(width), "check_path": False}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{url}?access_token={token}",
            content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=UTF-8"},
        )
        r.raise_for_status()
        data = r.content
    if data[:1] == b"{":
        try:
            err = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"wxacode invalid json: {data[:400]!r}") from e
        raise RuntimeError(f"wxacode api error: {err}")
    return data
