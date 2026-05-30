"""微信小程序虚拟支付（xpay）签名与查单。

道具直购 mode=short_series_goods；签名规则见微信《虚拟支付》文档：
- pay_sig = hex(hmac_sha256(appKey, uri + "&" + signData))
- signature = hex(hmac_sha256(session_key, signData))
其中 wx.requestVirtualPayment 场景 uri 固定为 ``requestVirtualPayment``；
后端 API（如 query_order）uri 为 ``/xpay/query_order``（带前导 ``/``）。
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx
import structlog

from app.config import settings
from app.core.exceptions import BadRequestError, ThirdPartyError
from app.integrations.wechat_access_token import get_access_token

logger = structlog.get_logger("wechat_xpay")

XPAY_QUERY_ORDER_URL = "https://api.weixin.qq.com/xpay/query_order"
XPAY_NOTIFY_PROVIDE_GOODS_URL = "https://api.weixin.qq.com/xpay/notify_provide_goods"
VIRTUAL_PAY_URI = "requestVirtualPayment"
QUERY_ORDER_URI = "/xpay/query_order"

# query_order.order.status：≥2 表示用户已支付（2 待发货，4 已发货）
XPAY_PAID_STATUSES = frozenset({2, 3, 4})


def xpay_env() -> int:
    return int(getattr(settings, "WECHAT_XPAY_ENV", 0) or 0)


def xpay_app_key() -> str:
    env = xpay_env()
    if env == 1:
        key = (getattr(settings, "WECHAT_XPAY_SANDBOX_APP_KEY", "") or "").strip()
        if not key:
            raise RuntimeError("WECHAT_XPAY_SANDBOX_APP_KEY 未配置（沙箱 env=1）")
        return key
    key = (getattr(settings, "WECHAT_XPAY_APP_KEY", "") or "").strip()
    if not key:
        raise RuntimeError("WECHAT_XPAY_APP_KEY 未配置")
    return key


def product_id_for_plan(plan_type: str) -> str:
    if plan_type == "monthly":
        pid = (getattr(settings, "WECHAT_XPAY_PRODUCT_MONTHLY", "") or "").strip()
    elif plan_type == "yearly":
        pid = (getattr(settings, "WECHAT_XPAY_PRODUCT_YEARLY", "") or "").strip()
    else:
        raise BadRequestError(code=40001, message=f"不支持的套餐：{plan_type}")
    if not pid:
        raise BadRequestError(
            code=40098,
            message=f"未配置虚拟支付道具 ID（plan={plan_type}）",
        )
    return pid


def calc_pay_sig(uri: str, sign_data_json: str, app_key: str | None = None) -> str:
    key = app_key if app_key is not None else xpay_app_key()
    msg = f"{uri}&{sign_data_json}"
    return hmac.new(key.encode(), msg.encode(), hashlib.sha256).hexdigest()


def calc_user_signature(sign_data_json: str, session_key: str) -> str:
    return hmac.new(session_key.encode(), sign_data_json.encode(), hashlib.sha256).hexdigest()


def build_sign_data(
    *,
    out_trade_no: str,
    plan_type: str,
    goods_price_cents: int,
    attach: str | None = None,
) -> dict[str, Any]:
    offer_id = (getattr(settings, "WECHAT_XPAY_OFFER_ID", "") or "").strip()
    if not offer_id:
        raise RuntimeError("WECHAT_XPAY_OFFER_ID 未配置")
    env = xpay_env()
    return {
        "offerId": offer_id,
        "buyQuantity": 1,
        "env": env,
        "currencyType": "CNY",
        "productId": product_id_for_plan(plan_type),
        "goodsPrice": int(goods_price_cents),
        "outTradeNo": out_trade_no,
        "attach": attach or plan_type,
    }


def dumps_sign_data(sign_data: dict[str, Any]) -> str:
    """紧凑 JSON，键序固定，避免签名不一致。"""
    return json.dumps(sign_data, ensure_ascii=False, separators=(",", ":"))


def build_virtual_prepay_params(
    *,
    out_trade_no: str,
    plan_type: str,
    goods_price_cents: int,
    session_key: str,
    attach: str | None = None,
) -> dict[str, str]:
    sign_data_obj = build_sign_data(
        out_trade_no=out_trade_no,
        plan_type=plan_type,
        goods_price_cents=goods_price_cents,
        attach=attach,
    )
    sign_data = dumps_sign_data(sign_data_obj)
    return {
        "sign_data": sign_data,
        "pay_sig": calc_pay_sig(VIRTUAL_PAY_URI, sign_data),
        "signature": calc_user_signature(sign_data, session_key),
        "mode": "short_series_goods",
    }


async def query_order(
    *,
    openid: str,
    order_id: str | None = None,
    wx_order_id: str | None = None,
) -> dict[str, Any]:
    if not order_id and not wx_order_id:
        raise BadRequestError(code=40002, message="query_order 需要 order_id 或 wx_order_id")

    body_obj = {
        "openid": openid,
        "env": xpay_env(),
    }
    if order_id:
        body_obj["order_id"] = order_id
    if wx_order_id:
        body_obj["wx_order_id"] = wx_order_id
    body_json = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":"))
    pay_sig = calc_pay_sig(QUERY_ORDER_URI, body_json)

    token = await get_access_token()
    url = f"{XPAY_QUERY_ORDER_URL}?access_token={token}&pay_sig={pay_sig}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, content=body_json, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.warning("xpay_query_order_http_error", error=str(e), order_id=order_id)
        raise ThirdPartyError(message="虚拟支付查单失败", detail=str(e)) from e
    except ValueError as e:
        raise ThirdPartyError(message="虚拟支付查单返回不可解析", detail=str(e)) from e

    errcode = data.get("errcode", 0)
    if errcode != 0:
        logger.warning(
            "xpay_query_order_failed",
            errcode=errcode,
            errmsg=data.get("errmsg"),
            order_id=order_id,
        )
        raise ThirdPartyError(
            message="虚拟支付查单失败",
            detail=f"errcode={errcode}, errmsg={data.get('errmsg')}",
        )
    return data


async def notify_provide_goods(
    *,
    order_id: str | None = None,
    wx_order_id: str | None = None,
) -> None:
    """异常补单：正常响应 xpay_goods_deliver_notify 后无需调用。"""
    if not order_id and not wx_order_id:
        raise BadRequestError(code=40002, message="notify_provide_goods 需要 order_id 或 wx_order_id")

    body_obj: dict[str, Any] = {"env": xpay_env()}
    if order_id:
        body_obj["order_id"] = order_id
    if wx_order_id:
        body_obj["wx_order_id"] = wx_order_id
    body_json = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":"))
    pay_sig = calc_pay_sig("/xpay/notify_provide_goods", body_json)

    token = await get_access_token()
    url = f"{XPAY_NOTIFY_PROVIDE_GOODS_URL}?access_token={token}&pay_sig={pay_sig}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, content=body_json, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.warning("xpay_notify_provide_goods_http_error", error=str(e))
        raise ThirdPartyError(message="虚拟支付通知发货失败", detail=str(e)) from e

    errcode = data.get("errcode", 0)
    if errcode != 0:
        raise ThirdPartyError(
            message="虚拟支付通知发货失败",
            detail=f"errcode={errcode}, errmsg={data.get('errmsg')}",
        )


def is_xpay_order_paid(order_payload: dict[str, Any]) -> bool:
    order = order_payload.get("order")
    if not isinstance(order, dict):
        return False
    try:
        status = int(order.get("status", -1))
    except (TypeError, ValueError):
        return False
    return status in XPAY_PAID_STATUSES
