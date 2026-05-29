"""M8-09 · 教练侧配额滥用风控（Redis 日计数）."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from app.config import settings
from app.core.exceptions import BadRequestError
from app.core.logging import get_logger

logger = get_logger("coach_abuse")

QuotaType = str  # "analysis" | "chat"


def _china_today_iso() -> str:
    now = datetime.now(UTC) + timedelta(hours=8)
    return now.strftime("%Y-%m-%d")


def _daily_limit(quota_type: QuotaType) -> int:
    if quota_type == "chat":
        return settings.COACH_CHAT_DAILY_LIMIT
    return settings.COACH_ANALYSIS_DAILY_LIMIT


async def track_coach_quota_usage(
    redis: Redis,
    *,
    user_id: str,
    quota_type: QuotaType,
) -> int:
    """教练 bypass 配额时仍计数，超限则限流（fail closed on abuse）."""
    key = f"coach_abuse:{user_id}:{_china_today_iso()}:{quota_type}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 86400)
    limit = _daily_limit(quota_type)
    if count > limit:
        logger.warning(
            "coach_quota_abuse_limit",
            extra={
                "user_id": user_id,
                "quota_type": quota_type,
                "count": count,
                "limit": limit,
            },
        )
        raise BadRequestError(
            code=40001,
            message="教练今日调用已达上限，请稍后再试",
        )
    return count
