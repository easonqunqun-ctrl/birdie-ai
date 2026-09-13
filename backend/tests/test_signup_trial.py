"""注册起 3 个月不限次，到期后每月 3 次."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.services import promo_service, quota_service
from app.services.signup_trial import is_signup_trial_active, trial_ends_at


def test_trial_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SIGNUP_TRIAL_MONTHS", 3)
    start = datetime(2026, 9, 13, 8, 0, tzinfo=UTC)
    user = User(id="usr_t1", invite_code="TRIAL001", created_at=start)
    assert trial_ends_at(user) == datetime(2026, 12, 13, 8, 0, tzinfo=UTC)
    assert is_signup_trial_active(user, now=start + timedelta(days=1))
    assert not is_signup_trial_active(user, now=datetime(2026, 12, 13, 8, 0, tzinfo=UTC))


def test_trial_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SIGNUP_TRIAL_MONTHS", 0)
    user = User(
        id="usr_t0",
        invite_code="TRIAL000",
        created_at=datetime.now(UTC),
    )
    assert is_signup_trial_active(user) is False


@pytest.mark.asyncio
async def test_me_unlimited_during_trial(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SIGNUP_TRIAL_MONTHS", 3)
    monkeypatch.setattr(settings, "QUOTA_MODE", "strict")
    resp = await client.get("/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["promo_free"]["active"] is True
    assert data["quota"]["analysis_remaining"] == -1
    assert data["quota"]["chat_remaining_today"] == -1
    assert data["quota"]["analysis_reset_at"] is None


@pytest.mark.asyncio
async def test_me_monthly_after_trial(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "SIGNUP_TRIAL_MONTHS", 3)
    monkeypatch.setattr(settings, "QUOTA_MODE", "strict")
    me = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    user_id = me["id"]
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        user.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        await db.commit()
    data = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert data["promo_free"]["active"] is False
    assert data["quota"]["analysis_remaining"] == 3
    assert data["quota"]["analysis_total"] == 3


def test_skip_history_paywall_in_trial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SIGNUP_TRIAL_MONTHS", 3)
    user = User(
        id="usr_pw",
        invite_code="PAYWALL1",
        created_at=datetime.now(UTC),
    )
    assert promo_service.should_skip_free_history_paywall(user) is True


def test_unlimited_user_uses_trial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SIGNUP_TRIAL_MONTHS", 3)
    monkeypatch.setattr(settings, "QUOTA_MODE", "strict")
    user = User(
        id="usr_ul",
        invite_code="UNLIM001",
        created_at=datetime.now(UTC),
        membership_type="free",
    )
    assert quota_service._is_unlimited_user(user) is True
