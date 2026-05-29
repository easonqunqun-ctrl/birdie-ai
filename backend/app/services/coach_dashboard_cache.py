"""M8-06 · 教练学员看板 Redis 缓存（TTL 30s）."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from redis.asyncio import Redis

from app.schemas.coach_dashboard import CoachDashboardDetailResponse, CoachDashboardListResponse

log = logging.getLogger(__name__)

LIST_PREFIX = "coach_dashboard:list:"
DETAIL_PREFIX = "coach_dashboard:detail:"
TTL_SECONDS = 30


def _list_key(coach_user_id: str) -> str:
    return f"{LIST_PREFIX}{coach_user_id}"


def _detail_key(coach_user_id: str, student_user_id: str) -> str:
    return f"{DETAIL_PREFIX}{coach_user_id}:{student_user_id}"


async def get_list_cache(
    redis: Redis | None, *, coach_user_id: str
) -> CoachDashboardListResponse | None:
    if redis is None:
        return None
    try:
        raw = await redis.get(_list_key(coach_user_id))
        if not raw:
            return None
        return CoachDashboardListResponse.model_validate(json.loads(raw))
    except Exception:
        log.warning("coach_dashboard_list_cache_read_failed", exc_info=True)
        return None


async def set_list_cache(
    redis: Redis | None,
    *,
    coach_user_id: str,
    payload: CoachDashboardListResponse,
) -> None:
    if redis is None:
        return
    try:
        await redis.setex(
            _list_key(coach_user_id),
            TTL_SECONDS,
            payload.model_dump_json(),
        )
    except Exception:
        log.warning("coach_dashboard_list_cache_write_failed", exc_info=True)


async def get_detail_cache(
    redis: Redis | None, *, coach_user_id: str, student_user_id: str
) -> CoachDashboardDetailResponse | None:
    if redis is None:
        return None
    try:
        raw = await redis.get(_detail_key(coach_user_id, student_user_id))
        if not raw:
            return None
        return CoachDashboardDetailResponse.model_validate(json.loads(raw))
    except Exception:
        log.warning("coach_dashboard_detail_cache_read_failed", exc_info=True)
        return None


async def set_detail_cache(
    redis: Redis | None,
    *,
    coach_user_id: str,
    student_user_id: str,
    payload: CoachDashboardDetailResponse,
) -> None:
    if redis is None:
        return
    try:
        await redis.setex(
            _detail_key(coach_user_id, student_user_id),
            TTL_SECONDS,
            payload.model_dump_json(),
        )
    except Exception:
        log.warning("coach_dashboard_detail_cache_write_failed", exc_info=True)


async def invalidate_coach_dashboard(
    redis: Redis | None, *, coach_user_id: str, student_user_id: str | None = None
) -> None:
    if redis is None:
        return
    try:
        keys = [_list_key(coach_user_id)]
        if student_user_id:
            keys.append(_detail_key(coach_user_id, student_user_id))
        if keys:
            await redis.delete(*keys)
    except Exception:
        log.warning("coach_dashboard_cache_invalidate_failed", exc_info=True)


def stamp_cached_at() -> datetime:
    return datetime.now(UTC)


__all__ = [
    "get_detail_cache",
    "get_list_cache",
    "invalidate_coach_dashboard",
    "set_detail_cache",
    "set_list_cache",
    "stamp_cached_at",
]
