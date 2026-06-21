"""公测免费 PROMO_FREE_UNTIL 行为."""

from datetime import datetime

import pytest

from app.config import settings
from app.services import promo_service


@pytest.fixture
def promo_until_july_30(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PROMO_FREE_UNTIL", "2026-07-30")
    monkeypatch.setattr(settings, "PROMO_FREE_SKIP_HISTORY_PAYWALL", True)


def test_inactive_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PROMO_FREE_UNTIL", "")
    assert promo_service.is_promo_free_active() is False


def test_active_on_until_day(promo_until_july_30: None) -> None:
    assert promo_service.is_promo_free_active(
        now=datetime(2026, 7, 30, 12, 0, 0),
    )


def test_inactive_after_until_day(promo_until_july_30: None) -> None:
    assert not promo_service.is_promo_free_active(
        now=datetime(2026, 7, 31, 0, 0, 1),
    )


def test_skip_paywall_when_active(promo_until_july_30: None) -> None:
    assert promo_service.should_skip_free_history_paywall() is True


def test_status_label(promo_until_july_30: None) -> None:
    status = promo_service.status_for_response()
    assert status.active is True
    assert status.until == "2026-07-30"
    assert status.message and "公测免费" in status.message
