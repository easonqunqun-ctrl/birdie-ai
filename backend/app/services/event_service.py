"""埋点 / 错误上报服务（W8-T5）。

职责
----
- 批量接收前端 `track.ts` flush 的事件并落到 `events` 表
- 校验事件名白名单 + payload 大小上限，避免客户端把任意数据塞进来
- 允许匿名（未登录）上报，便于首启前的 `App.onError` 也能收集

白名单
------
W8 版本定义 6 个核心事件 + error_report，其它名字的事件会被拒绝（但整批不
失败，只标记 `rejected` 计数返回给客户端）。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import new_id
from app.models.event import Event

logger = get_logger("event_service")

# W8-T5 核心事件白名单（见 docs/16 T5）+ PP-05 公测漏斗
#   - page_view         首页 / 关键页访问
#   - analysis_submit   用户提交分析任务
#   - analysis_done     报告页首次可见
#   - share_report      用户触发分享（朋友 / 朋友圈）
#   - pay_success       支付成功（mock / real 都打同一个事件名）
#   - error_report      前端运行期错误（App.onError / onUnhandledRejection）
#   - membership_view   进入会员中心（PP-05）
#   - upgrade_cta_click 点击开通/续费 CTA（PP-05）
EVENT_NAMES: frozenset[str] = frozenset(
    {
        "page_view",
        "analysis_submit",
        "analysis_done",
        "share_report",
        "pay_success",
        "error_report",
        "membership_view",
        "upgrade_cta_click",
    }
)

# 单事件 payload JSON 序列化后大小上限；超了会被裁掉（防止恶意塞大对象）
MAX_PAYLOAD_BYTES = 8 * 1024

# 单次批量接口最多接受的事件数
MAX_BATCH_SIZE = 50


async def insert_events(
    db: AsyncSession,
    user_id: str | None,
    batch: Iterable[dict[str, Any]],
) -> tuple[int, int]:
    """批量落库事件。

    Args:
        db: AsyncSession（由调用方控制 commit 时机）
        user_id: 当前登录用户 ID；匿名传 None
        batch: 可迭代的 dict，每个 dict 必须含 `name`，可选 `payload`、`client_ts`

    Returns:
        (accepted_count, rejected_count)
    """
    accepted = 0
    rejected = 0
    for idx, raw in enumerate(batch):
        if idx >= MAX_BATCH_SIZE:
            rejected += 1
            continue
        name = raw.get("name")
        if not isinstance(name, str) or name not in EVENT_NAMES:
            logger.debug("event_name_rejected", name=name)
            rejected += 1
            continue

        payload = raw.get("payload")
        if payload is not None:
            payload = _truncate_payload(payload)

        client_ts_raw = raw.get("client_ts")
        client_ts = _parse_client_ts(client_ts_raw)

        db.add(
            Event(
                id=new_id("evt"),
                user_id=user_id,
                name=name,
                payload=payload,
                client_ts=client_ts,
            )
        )
        accepted += 1

    if accepted > 0:
        await db.flush()

    return accepted, rejected


def _truncate_payload(payload: Any) -> Any:
    """若 payload 大于上限，返回一个提示性的截断对象，避免单条 event 过大。"""
    # 只接受 dict/list 顶层；其它类型包一层 dict
    if not isinstance(payload, (dict, list)):
        payload = {"value": payload}

    import json

    try:
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return {"_truncated": True, "_reason": "not_json_serializable"}

    if len(serialized.encode("utf-8")) <= MAX_PAYLOAD_BYTES:
        return payload
    logger.debug(
        "event_payload_truncated", size=len(serialized), limit=MAX_PAYLOAD_BYTES
    )
    return {
        "_truncated": True,
        "_preview": serialized[:512],
    }


def _parse_client_ts(raw: Any) -> datetime | None:
    """接受 ms 时间戳（number / 数字字符串）或 ISO 8601 字符串；非法值返回 None。"""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw / 1000 if raw > 1e12 else raw)
        except (OSError, ValueError, OverflowError):
            return None
    if isinstance(raw, str):
        try:
            # 数字字符串（前端常用）
            num = float(raw)
            return datetime.fromtimestamp(num / 1000 if num > 1e12 else num)
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
