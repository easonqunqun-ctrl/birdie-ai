"""微信小程序 API 封装：code2session 等."""

import hashlib

import httpx

from app.config import settings
from app.core.exceptions import ThirdPartyError
from app.core.logging import get_logger

logger = get_logger("wechat")

CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


class WechatSession:
    """code2session 返回结果."""

    def __init__(self, openid: str, session_key: str, unionid: str | None = None) -> None:
        self.openid = openid
        self.session_key = session_key
        self.unionid = unionid


async def code2session(code: str) -> WechatSession:
    """用 wx.login 的临时 code 换取 openid + session_key.

    本地开发模式（WECHAT_MOCK_LOGIN=true）会基于 code 生成稳定的 mock openid，
    便于联调时同一 code 映射到同一虚拟用户。
    """
    if settings.WECHAT_MOCK_LOGIN:
        # mock: 用 code 哈希作为稳定 openid
        digest = hashlib.sha256(code.encode()).hexdigest()[:24]
        return WechatSession(
            openid=f"mock_openid_{digest}",
            session_key=f"mock_sk_{digest}",
            unionid=None,
        )

    params = {
        "appid": settings.WECHAT_MINIPROGRAM_APPID,
        "secret": settings.WECHAT_MINIPROGRAM_SECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(CODE2SESSION_URL, params=params)
            data = resp.json()
    except Exception as e:
        logger.error("wechat_code2session_error", error=str(e))
        raise ThirdPartyError(code=50201, message="微信服务异常", detail=str(e)) from e

    if "errcode" in data and data["errcode"] != 0:
        logger.warning("wechat_code2session_failed", **data)
        raise ThirdPartyError(
            code=50201,
            message="微信登录失败",
            detail=f"errcode={data.get('errcode')}, errmsg={data.get('errmsg')}",
        )

    return WechatSession(
        openid=data["openid"],
        session_key=data["session_key"],
        unionid=data.get("unionid"),
    )
