"""全局公测窗 + 注册免费体验（至截止日期 inclusive / 注册 + N 月）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config import settings
from app.schemas.user import PromoFreeStatus


def _parse_until_date(raw: str) -> datetime.date | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _now_cst() -> datetime:
    return datetime.now(UTC) + timedelta(hours=8)


def is_promo_free_active(*, now: datetime | None = None) -> bool:
    """``PROMO_FREE_UNTIL=YYYY-MM-DD`` 当天 23:59:59 (UTC+8) 前视为全员免费."""
    until = _parse_until_date(settings.PROMO_FREE_UNTIL)
    if until is None:
        return False
    ref = (now or _now_cst()).replace(tzinfo=None)
    return ref.date() <= until


def promo_free_until_iso() -> str | None:
    until = _parse_until_date(settings.PROMO_FREE_UNTIL)
    return until.isoformat() if until else None


def should_skip_free_history_paywall(user=None) -> bool:
    if user is not None:
        from app.services.signup_trial import is_signup_trial_active

        if is_signup_trial_active(user):
            return True
    return (
        settings.PROMO_FREE_SKIP_HISTORY_PAYWALL and is_promo_free_active()
    )


def status_for_response(user=None) -> PromoFreeStatus:
    if user is not None:
        from app.services.signup_trial import (
            is_signup_trial_active,
            trial_until_iso_date,
        )

        if is_signup_trial_active(user):
            until = trial_until_iso_date(user)
            message = f"新用户免费体验至 {until}" if until else "新用户免费体验中"
            return PromoFreeStatus(active=True, until=until, message=message)
    active = is_promo_free_active()
    until = promo_free_until_iso()
    message = f"公测免费至 {until}" if active and until else None
    return PromoFreeStatus(active=active, until=until, message=message)
