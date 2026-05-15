"""微信小程序 API 封装：code2session 与移动应用 OAuth2."""

import hashlib

import httpx

from app.config import settings
from app.core.exceptions import ThirdPartyError, UnauthorizedError
from app.core.logging import get_logger

logger = get_logger("wechat")

CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
OAUTH2_ACCESS_TOKEN_APP_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"

# W8-T4：用户原因导致的微信侧失败码（应映射 401，让客户端引导用户重新 wx.login）
# 文档：https://developers.weixin.qq.com/miniprogram/dev/api-backend/open-api/login/auth.code2Session.html
#   40029 - js_code 无效（最常见：客户端拿到 code 拖太久，> 5 分钟）
#   40163 - code 已被使用（同一 code 二次提交）
#   -1    - 系统繁忙（理论上是临时错误，但实务也常因 code 已过期触发；归到用户侧让前端重试更友好）
USER_FAULT_ERRCODES: frozenset[int] = frozenset({40029, 40163, -1})


class WechatSession:
    """code2session 返回结果."""

    def __init__(self, openid: str, session_key: str, unionid: str | None = None) -> None:
        self.openid = openid
        self.session_key = session_key
        self.unionid = unionid


class WechatAppOAuthSession:
    """微信开放平台 · 移动应用 OAuth2：`authorization_code` 换 access_token."""

    __slots__ = ("app_openid", "unionid")

    def __init__(self, app_openid: str, unionid: str | None = None) -> None:
        self.app_openid = app_openid
        self.unionid = unionid


async def code2session(code: str) -> WechatSession:
    """用 wx.login 的临时 code 换取 openid + session_key.

    本地开发模式（WECHAT_MOCK_LOGIN=true）会基于 code 生成稳定的 mock openid，
    便于联调时同一 code 映射到同一虚拟用户。

    错误映射（W8-T4）：
      - 用户侧错误（USER_FAULT_ERRCODES，code 失效/重复使用/系统繁忙）→ UnauthorizedError 40104
        前端应清掉本地 token、再次 wx.login 拿新 code 重试
      - 第三方系统侧错误（appid/secret 错、配额超限、HTTP 5xx、网络异常）→ ThirdPartyError 50201
        前端应 toast"微信服务异常，请稍后再试"
    """
    if settings.WECHAT_MOCK_LOGIN:
        # mock: 与 open-app oauth 共用同一 digest，便于 W10 串联「小程序登录 + App 登录」合并 unionid。
        digest = hashlib.sha256(code.encode()).hexdigest()[:24]
        uni = f"mock_union_{digest}"
        return WechatSession(
            openid=f"mock_openid_{digest}",
            session_key=f"mock_sk_{digest}",
            unionid=uni,
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
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        # 网络超时 / DNS / 5xx / TLS 等都是"我们这一侧"打不通微信
        logger.error("wechat_code2session_http_error", error=str(e))
        raise ThirdPartyError(
            code=50201, message="微信服务异常", detail=str(e)
        ) from e
    except ValueError as e:
        # JSON 解析失败：微信极少返回非 JSON，但被劫持/中转响应可能出现
        logger.error("wechat_code2session_decode_error", error=str(e))
        raise ThirdPartyError(
            code=50201, message="微信服务返回不可解析", detail=str(e)
        ) from e

    if "errcode" in data and data["errcode"] != 0:
        errcode = data.get("errcode")
        errmsg = data.get("errmsg")
        # 用户侧错误：4xx 让客户端走"重新 wx.login"流程
        if errcode in USER_FAULT_ERRCODES:
            logger.info("wechat_code2session_user_fault", errcode=errcode, errmsg=errmsg)
            raise UnauthorizedError(
                code=40104,
                message="微信登录凭证已失效，请重试",
                detail=f"errcode={errcode}, errmsg={errmsg}",
            )
        # 系统侧错误（appid/secret 错配、API 超限等）：交给运维排查
        logger.warning("wechat_code2session_system_fault", errcode=errcode, errmsg=errmsg)
        raise ThirdPartyError(
            code=50201,
            message="微信登录失败",
            detail=f"errcode={errcode}, errmsg={errmsg}",
        )

    return WechatSession(
        openid=data["openid"],
        session_key=data["session_key"],
        unionid=data.get("unionid"),
    )


async def oauth2_access_token_app(code: str) -> WechatAppOAuthSession:
    """移动应用：用 App 拉起微信授权返回的临时 code，换用户 openid/unionid.

    docs: https://developers.weixin.qq.com/doc/oplatform/Mobile_App/WeChat_Login/Development_Guide_Android.html

    MOCK 模式下与小程序 mock 对齐同一 digest，便于内测串联账号合并逻辑。
    """
    if settings.WECHAT_MOCK_LOGIN:
        digest = hashlib.sha256(code.encode()).hexdigest()[:24]
        return WechatAppOAuthSession(
            app_openid=f"mock_app_openid_{digest}",
            unionid=f"mock_union_{digest}",
        )

    params = {
        "appid": settings.WECHAT_OPEN_APPID,
        "secret": settings.WECHAT_OPEN_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(OAUTH2_ACCESS_TOKEN_APP_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error("wechat_oauth_http_error", error=str(e))
        raise ThirdPartyError(
            code=50201, message="微信服务异常", detail=str(e)
        ) from e
    except ValueError as e:
        logger.error("wechat_oauth_decode_error", error=str(e))
        raise ThirdPartyError(
            code=50201, message="微信服务返回不可解析", detail=str(e)
        ) from e

    if data.get("errcode"):
        errcode = data.get("errcode")
        errmsg = data.get("errmsg")
        if errcode in USER_FAULT_ERRCODES:
            logger.info("wechat_oauth_user_fault", errcode=errcode, errmsg=errmsg)
            raise UnauthorizedError(
                code=40104,
                message="微信登录凭证已失效，请重试",
                detail=f"errcode={errcode}, errmsg={errmsg}",
            )
        logger.warning("wechat_oauth_system_fault", errcode=errcode, errmsg=errmsg)
        raise ThirdPartyError(
            code=50201,
            message="微信开放平台登录失败",
            detail=f"errcode={errcode}, errmsg={errmsg}",
        )

    openid_app = data.get("openid")
    if not isinstance(openid_app, str) or not openid_app.strip():
        raise ThirdPartyError(
            code=50201,
            message="微信开放平台返回缺少 openid",
            detail=str(data),
        )

    return WechatAppOAuthSession(
        openid_app,
        unionid=data.get("unionid"),
    )

