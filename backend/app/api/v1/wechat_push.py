"""微信小程序消息推送（虚拟支付发货等 Event）。

配置路径：mp 后台 → 开发 → 开发管理 → 消息推送
URL 示例：https://api.birdieai.cn/v1/wechat/mp-push
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.services import payment_service

router = APIRouter()
logger = structlog.get_logger("wechat_mp_push")


def _verify_signature(token: str, timestamp: str, nonce: str, signature: str) -> bool:
    if not token or not signature:
        return False
    arr = sorted([token, timestamp, nonce])
    digest = hashlib.sha1("".join(arr).encode()).hexdigest()
    return digest == signature


def _parse_xml_body(raw: bytes) -> dict[str, str]:
    root = ET.fromstring(raw)
    out: dict[str, str] = {}
    for child in root:
        if child.text is not None:
            out[child.tag] = child.text
    return out


def _extract_event_payload(body: bytes, content_type: str) -> dict:
    ct = (content_type or "").lower()
    if "json" in ct or body.lstrip().startswith(b"{"):
        data = json.loads(body.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("json root not object")
        return data
    return _parse_xml_body(body)


@router.get(
    "/mp-push",
    summary="微信小程序消息推送 URL 验证",
    include_in_schema=False,
)
async def wechat_mp_push_verify(
    signature: str = Query(alias="signature"),
    timestamp: str = Query(alias="timestamp"),
    nonce: str = Query(alias="nonce"),
    echostr: str = Query(alias="echostr"),
) -> PlainTextResponse:
    token = (settings.WECHAT_MP_PUSH_TOKEN or "").strip()
    if not token:
        return PlainTextResponse("token not configured", status_code=503)
    if _verify_signature(token, timestamp, nonce, signature):
        return PlainTextResponse(echostr)
    return PlainTextResponse("invalid signature", status_code=403)


@router.post(
    "/mp-push",
    summary="微信小程序消息推送（xpay_goods_deliver_notify 等）",
    include_in_schema=False,
)
async def wechat_mp_push_event(
    request: Request,
    signature: str = Query(default="", alias="signature"),
    timestamp: str = Query(default="", alias="timestamp"),
    nonce: str = Query(default="", alias="nonce"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    token = (settings.WECHAT_MP_PUSH_TOKEN or "").strip()
    if not token:
        return PlainTextResponse("token not configured", status_code=503)

    if signature and not _verify_signature(token, timestamp, nonce, signature):
        logger.warning("wechat_mp_push_bad_signature")
        return PlainTextResponse("invalid signature", status_code=403)

    body = await request.body()
    content_type = request.headers.get("content-type", "")

    try:
        payload = _extract_event_payload(body, content_type)
    except (ET.ParseError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
        logger.warning("wechat_mp_push_parse_error", error=str(e))
        return Response(
            content=json.dumps({"ErrCode": -1, "ErrMsg": "parse error"}),
            media_type="application/json",
            status_code=200,
        )

    event = (payload.get("Event") or payload.get("event") or "").strip()
    logger.info("wechat_mp_push_received", event=event)

    if event == "xpay_goods_deliver_notify":
        try:
            ok, msg = await payment_service.process_xpay_goods_deliver_notify(db, payload)
            if ok:
                await db.commit()
                return Response(
                    content=json.dumps({"ErrCode": 0, "ErrMsg": "success"}),
                    media_type="application/json",
                    status_code=200,
                )
            await db.rollback()
            logger.warning("xpay_goods_deliver_notify_failed", detail=msg)
            return Response(
                content=json.dumps({"ErrCode": -1, "ErrMsg": msg}),
                media_type="application/json",
                status_code=200,
            )
        except Exception as e:
            await db.rollback()
            logger.exception("xpay_goods_deliver_notify_exception", error=str(e))
            return Response(
                content=json.dumps({"ErrCode": -1, "ErrMsg": "internal error"}),
                media_type="application/json",
                status_code=200,
            )

    # 其它 Event：幂等成功，避免微信反复重试
    return Response(
        content=json.dumps({"ErrCode": 0, "ErrMsg": "ignored"}),
        media_type="application/json",
        status_code=200,
    )
