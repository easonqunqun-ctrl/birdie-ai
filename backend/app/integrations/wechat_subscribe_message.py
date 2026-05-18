"""微信小程序「一次性订阅消息」服务端下发（分析完成提醒等）.

文档：<https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/mp-message-management/subscribe-message/sendMessage.html>

前置条件：
- 用户在小程序内已对对应 `template_id` 调用 `wx.requestSubscribeMessage` 并接受；
- 后端配置 `WECHAT_SUBSCRIBE_MESSAGE_ENABLED=true`；
- **分析完成**：`WECHAT_SUBSCRIBE_ANALYSIS_TEMPLATE_ID` 与客户端 `TARO_APP_SUBSCRIBE_TMPL_IDS` **首项**、公众平台模板一致；数据字段 **thing1 + number2 + time3**。
- **会员到期**：`WECHAT_SUBSCRIBE_MEMBERSHIP_EXPIRE_TEMPLATE_ID` 与客户端 **第二项**、公众平台模板一致；数据字段 **thing1 + time2 + thing3**（见 `send_membership_expired_notification`）。
- **到期前提醒**：`WECHAT_SUBSCRIBE_MEMBERSHIP_PRE_EXPIRE_TEMPLATE_ID` 与客户端 **第三项** 一致；字段布局与「已到期」模板相同，文案不同（见 `send_membership_pre_expiry_notification`）。
- 运营建模板时须对齐关键字类型；否则微信返回 errcode，仅记日志。
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.integrations.wechat_access_token import get_access_token

logger = get_logger("wechat_subscribe_message")

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
SUBSCRIBE_SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"

# 用户拒绝 / 无次数等非致命错误（不打扰分析主流程）
_BENIGN_SUBSCRIBE_ERRCODES: frozenset[int] = frozenset(
    {
        43101,  # 用户拒绝接受消息
        47003,  # 次数用尽 / 未订阅
        40003,  # openid 无效
    }
)


def _fmt_analyzed_at_sh(dt: datetime | None) -> str:
    if dt is None:
        return datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M")


async def send_analysis_completed_notification(
    *,
    openid: str | None,
    analysis_id: str,
    overall_score: int | None,
    analyzed_at: datetime | None,
) -> None:
    """分析成功后尝试推送「分析完成」订阅消息（失败仅打日志）。"""
    if not settings.WECHAT_SUBSCRIBE_MESSAGE_ENABLED:
        return
    tid = (settings.WECHAT_SUBSCRIBE_ANALYSIS_TEMPLATE_ID or "").strip()
    if not tid or not openid or not openid.strip():
        return
    if settings.WECHAT_MOCK_LOGIN or openid.startswith("mock_"):
        return

    score_text = str(int(overall_score)) if overall_score is not None else "--"
    thing1 = "挥杆分析报告已生成"
    payload = {
        "touser": openid.strip(),
        "template_id": tid,
        "page": f"pages/analysis/report?id={analysis_id}",
        "miniprogram_state": settings.WECHAT_SUBSCRIBE_MINIPROGRAM_STATE,
        "lang": "zh_CN",
        "data": {
            "thing1": {"value": thing1[:20]},
            "number2": {"value": score_text[:32]},
            "time3": {"value": _fmt_analyzed_at_sh(analyzed_at)[:20]},
        },
    }

    await _post_subscribe_send(payload, retried=False)


async def send_membership_expired_notification(
    *,
    openid: str | None,
    expired_at: datetime,
) -> None:
    """会员因到期被惰性降级时尝试推送「会员已到期」订阅消息（失败仅打日志）。

    触发：`payment_service.ensure_membership_valid` 检测到 `membership_expires_at <= now`
    后完成降级与 flush，再调用本函数。用户须已在会员页对第二模板授权。
    """
    if not settings.WECHAT_SUBSCRIBE_MESSAGE_ENABLED:
        return
    tid = (settings.WECHAT_SUBSCRIBE_MEMBERSHIP_EXPIRE_TEMPLATE_ID or "").strip()
    if not tid or not openid or not openid.strip():
        return
    if settings.WECHAT_MOCK_LOGIN or openid.startswith("mock_"):
        return

    if expired_at.tzinfo is None:
        expired_at = expired_at.replace(tzinfo=UTC)
    time_str = expired_at.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M")
    thing1 = "会员权益已到期"
    thing3 = "打开小程序续费"
    payload = {
        "touser": openid.strip(),
        "template_id": tid,
        "page": "pages/profile/membership",
        "miniprogram_state": settings.WECHAT_SUBSCRIBE_MINIPROGRAM_STATE,
        "lang": "zh_CN",
        "data": {
            "thing1": {"value": thing1[:20]},
            "time2": {"value": time_str[:20]},
            "thing3": {"value": thing3[:20]},
        },
    }

    await _post_subscribe_send(payload, retried=False)


async def send_membership_pre_expiry_notification(
    *,
    openid: str | None,
    expires_at: datetime,
) -> None:
    """会员到期日前第 N 天（由 Celery 任务按上海日历判定）推送「即将到期」订阅消息。

    用户须在会员页对 `TARO_APP_SUBSCRIBE_TMPL_IDS` 第三项授权；失败仅打日志。
    """
    if not settings.WECHAT_SUBSCRIBE_MESSAGE_ENABLED:
        return
    tid = (settings.WECHAT_SUBSCRIBE_MEMBERSHIP_PRE_EXPIRE_TEMPLATE_ID or "").strip()
    if not tid or not openid or not openid.strip():
        return
    if settings.WECHAT_MOCK_LOGIN or openid.startswith("mock_"):
        return

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    time_str = expires_at.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M")
    thing1 = "会员权益即将到期"
    thing3 = "打开小程序续费"
    payload = {
        "touser": openid.strip(),
        "template_id": tid,
        "page": "pages/profile/membership",
        "miniprogram_state": settings.WECHAT_SUBSCRIBE_MINIPROGRAM_STATE,
        "lang": "zh_CN",
        "data": {
            "thing1": {"value": thing1[:20]},
            "time2": {"value": time_str[:20]},
            "thing3": {"value": thing3[:20]},
        },
    }

    await _post_subscribe_send(payload, retried=False)


async def _post_subscribe_send(body: dict, *, retried: bool) -> None:
    try:
        access_token = await get_access_token()
    except Exception as exc:
        logger.warning("subscribe_message.access_token_failed", error=str(exc))
        return

    if access_token == "mock_access_token":
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                SUBSCRIBE_SEND_URL,
                params={"access_token": access_token},
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("subscribe_message.http_error", error=str(exc))
        return
    except ValueError as exc:
        logger.warning("subscribe_message.json_error", error=str(exc))
        return

    err = int(data.get("errcode", 0) or 0)
    if err == 0:
        logger.info("subscribe_message.sent_ok", msgid=data.get("msgid"))
        return

    # access_token 过期：强制刷新重试一次
    if err in (40001, 42001) and not retried:
        try:
            access_token = await get_access_token(force_refresh=True)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    SUBSCRIBE_SEND_URL,
                    params={"access_token": access_token},
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
            err2 = int(data.get("errcode", 0) or 0)
            if err2 == 0:
                logger.info("subscribe_message.sent_ok_retry", msgid=data.get("msgid"))
                return
            err = err2
        except Exception as exc:
            logger.warning("subscribe_message.retry_failed", error=str(exc))
            return

    if err in _BENIGN_SUBSCRIBE_ERRCODES:
        logger.info(
            "subscribe_message.benign_skip",
            errcode=err,
            errmsg=data.get("errmsg"),
        )
        return

    logger.warning(
        "subscribe_message.send_failed",
        errcode=err,
        errmsg=data.get("errmsg"),
    )
