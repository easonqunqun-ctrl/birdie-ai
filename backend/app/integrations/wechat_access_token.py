"""微信小程序 access_token 获取 + Redis 缓存（W8-T5）。

设计要点
---------
1. 全局 access_token（`/cgi-bin/token`）是**小程序级别**的共享令牌：
   - 同一个 AppID 拿到的 token，所有后端实例都能用
   - 微信侧 TTL = 7200s（2 小时）；每天有调用量限制，严禁频繁刷
2. 缓存层：Redis key `wechat:access_token`，TTL = `expires_in - 300`（提前 5 分钟
   让下一次调用去主动刷新，避免卡在"刚好过期"的竞争窗口）
3. mock 模式（`WECHAT_MOCK_LOGIN=true`）完全跳过网络，返回固定 fake token；
   由此 `imgSecCheck` 在本地开发时会走 mock 分支（见 `wechat_security.py`）
4. 并发安全：多请求同时 miss 时，会出现短时多次调微信——但微信 `/cgi-bin/token`
   对同 appid 不做互斥，新 token 会覆盖旧 token（旧 token 在原 TTL 内仍可用），
   所以不加分布式锁也能接受；等真出现瓶颈再加
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.core.exceptions import ThirdPartyError
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger("wechat_access_token")

ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
REDIS_KEY = "wechat:access_token"
REFRESH_LEAD_SECONDS = 300  # 提前 5 分钟失效，避免 token 刚好在调用微信 API 时过期


async def get_access_token(force_refresh: bool = False) -> str:
    """取微信小程序全局 access_token。

    Args:
        force_refresh: True 时跳过 Redis 缓存，强制从微信拉新 token。
            典型场景：上一次 imgSecCheck 返回 42001（token 过期）→ 重试一次。

    Returns:
        access_token 字符串。

    Raises:
        ThirdPartyError: 微信返回 errcode != 0，或 HTTP/JSON 异常。
    """
    if settings.WECHAT_MOCK_LOGIN:
        # mock 环境：不打真实微信，返回固定字符串；下游 imgSecCheck 也会走 mock 分支
        return "mock_access_token"

    redis = await get_redis()
    if not force_refresh:
        cached = await redis.get(REDIS_KEY)
        if cached:
            return cached

    params = {
        "grant_type": "client_credential",
        "appid": settings.WECHAT_MINIPROGRAM_APPID,
        "secret": settings.WECHAT_MINIPROGRAM_SECRET,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(ACCESS_TOKEN_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error("wechat_access_token_http_error", error=str(e))
        raise ThirdPartyError(
            code=50201, message="微信服务异常", detail=f"获取 access_token 失败：{e}"
        ) from e
    except ValueError as e:
        logger.error("wechat_access_token_decode_error", error=str(e))
        raise ThirdPartyError(
            code=50201, message="微信服务返回不可解析", detail=str(e)
        ) from e

    if "errcode" in data and data["errcode"] != 0:
        logger.warning("wechat_access_token_failed", **data)
        raise ThirdPartyError(
            code=50201,
            message="微信 access_token 获取失败",
            detail=f"errcode={data.get('errcode')}, errmsg={data.get('errmsg')}",
        )

    token: str = data["access_token"]
    expires_in: int = int(data.get("expires_in", 7200))
    ttl = max(expires_in - REFRESH_LEAD_SECONDS, 60)
    await redis.set(REDIS_KEY, token, ex=ttl)
    logger.info("wechat_access_token_refreshed", expires_in=expires_in, ttl=ttl)
    return token
