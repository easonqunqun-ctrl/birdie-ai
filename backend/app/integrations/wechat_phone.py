"""微信小程序 · 手机号快速验证（getPhoneNumber code → 明文手机号）."""

from __future__ import annotations

import httpx

from app.config import settings
from app.core.exceptions import ThirdPartyError, UnauthorizedError
from app.core.logging import get_logger
from app.integrations.wechat import USER_FAULT_ERRCODES
from app.integrations.wechat_access_token import get_access_token

logger = get_logger("wechat_phone")

GET_PHONE_URL = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"


class WechatPhoneInfo:
    __slots__ = ("country_code", "phone_number", "pure_phone_number")

    def __init__(
        self,
        *,
        phone_number: str,
        pure_phone_number: str,
        country_code: str,
    ) -> None:
        self.phone_number = phone_number
        self.pure_phone_number = pure_phone_number
        self.country_code = country_code


async def get_user_phone_number(phone_code: str) -> WechatPhoneInfo:
    """用 `getPhoneNumber` 按钮返回的 code 换取用户手机号."""

    code = phone_code.strip()
    if not code:
        raise ThirdPartyError(code=50201, message="微信手机号凭证无效", detail="empty code")

    if settings.WECHAT_MOCK_LOGIN:
        return WechatPhoneInfo(
            phone_number="+8613800138000",
            pure_phone_number="13800138000",
            country_code="86",
        )

    token = await get_access_token()
    url = f"{GET_PHONE_URL}?access_token={token}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"code": code})
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error("wechat_get_phone_http_error", error=str(e))
        raise ThirdPartyError(
            code=50201, message="微信服务异常", detail=f"getuserphonenumber 失败：{e}"
        ) from e
    except ValueError as e:
        logger.error("wechat_get_phone_decode_error", error=str(e))
        raise ThirdPartyError(
            code=50201, message="微信服务返回不可解析", detail=str(e)
        ) from e

    errcode = data.get("errcode", 0)
    if errcode != 0:
        errmsg = data.get("errmsg")
        if errcode in USER_FAULT_ERRCODES:
            logger.info("wechat_get_phone_user_fault", errcode=errcode, errmsg=errmsg)
            raise UnauthorizedError(
                code=40104,
                message="手机号授权已失效，请重新点击授权",
                detail=f"errcode={errcode}, errmsg={errmsg}",
            )
        logger.warning("wechat_get_phone_system_fault", errcode=errcode, errmsg=errmsg)
        raise ThirdPartyError(
            code=50201,
            message="微信手机号验证失败",
            detail=f"errcode={errcode}, errmsg={errmsg}",
        )

    info = data.get("phone_info") or {}
    pure = info.get("purePhoneNumber") or info.get("phoneNumber")
    if not isinstance(pure, str) or not pure.strip():
        raise ThirdPartyError(
            code=50201,
            message="微信未返回手机号",
            detail=str(data),
        )

    phone_number = info.get("phoneNumber") if isinstance(info.get("phoneNumber"), str) else pure
    country = info.get("countryCode")
    country_code = str(country) if country is not None else "86"

    return WechatPhoneInfo(
        phone_number=phone_number.strip(),
        pure_phone_number=pure.strip(),
        country_code=country_code,
    )
