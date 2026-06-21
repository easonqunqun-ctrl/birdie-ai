"""公测免费促销（至 PROMO_FREE_UNTIL  inclusive，按 UTC+8 自然日）."""

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
    """``PROMO_FREE_UNTIL=YYYY-MM-DD`` 当天 23:59:59 (UTC+8) 前视为公测免费."""
    until = _parse_until_date(settings.PROMO_FREE_UNTIL)
    if until is None:
        return False
    ref = (now or _now_cst()).replace(tzinfo=None)
    return ref.date() <= until


def promo_free_until_iso() -> str | None:
    until = _parse_until_date(settings.PROMO_FREE_UNTIL)
    return until.isoformat() if until else None


def should_skip_free_history_paywall() -> bool:
    return (
        settings.PROMO_FREE_SKIP_HISTORY_PAYWALL and is_promo_free_active()
    )


def status_for_response() -> PromoFreeStatus:
    active = is_promo_free_active()
    until = promo_free_until_iso()
    message = f"公测免费至 {until}" if active and until else None
    return PromoFreeStatus(active=active, until=until, message=message)
