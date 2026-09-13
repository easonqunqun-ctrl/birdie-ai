"""注册日起算的免费体验期（docs/01 §2.2.1）。"""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.models.user import User


def _add_months(dt: datetime, months: int) -> datetime:
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def trial_months() -> int:
    return max(0, int(settings.SIGNUP_TRIAL_MONTHS))


def trial_ends_at(user: User) -> datetime | None:
    months = trial_months()
    if months <= 0 or user.created_at is None:
        return None
    start = user.created_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    return _add_months(start, months)


def is_signup_trial_active(user: User, *, now: datetime | None = None) -> bool:
    end = trial_ends_at(user)
    if end is None:
        return False
    ref = now or datetime.now(UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    return ref < end


def trial_until_iso_date(user: User) -> str | None:
    """UTC+8 自然日，给客户端 banner 用。"""
    end = trial_ends_at(user)
    if end is None:
        return None
    cst = end.astimezone(UTC) + timedelta(hours=8)
    return cst.date().isoformat()
