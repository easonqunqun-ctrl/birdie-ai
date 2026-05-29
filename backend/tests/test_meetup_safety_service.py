"""M13-09 meetup_safety_service 单测."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import (
    MeetupIdentityRequiredError,
    MeetupMinorBlockedError,
    MeetupTosRequiredError,
)
from app.core.security import new_id
from app.models.user import User
from app.services import meetup_safety_service as safety_svc


async def _make_user(
    db: AsyncSession,
    *,
    birth_date: date | None = None,
    phone_verified: bool = False,
    gender: str | None = None,
) -> User:
    u = User(
        id=new_id("usr"),
        wechat_openid=f"o_{new_id('mock')}",
        nickname="t",
        invite_code=new_id("inv")[-6:].upper(),
        birth_date=birth_date,
        phone_verified_at=datetime.now(UTC) if phone_verified else None,
        gender=gender,
    )
    db.add(u)
    await db.flush()
    return u


def test_user_age_years() -> None:
    user = User(
        id="usr_x",
        invite_code="ABC123",
        birth_date=date(2010, 5, 29),
    )
    assert safety_svc.user_age_years(user, on_date=date(2026, 5, 29)) == 16


@pytest.mark.asyncio
async def test_assert_identity_blocks_minor() -> None:
    async with AsyncSessionLocal() as db:
        minor = await _make_user(
            db,
            birth_date=date(2015, 1, 1),
            phone_verified=True,
        )
        with pytest.raises(MeetupMinorBlockedError) as exc:
            safety_svc.assert_identity_eligible(minor)
        assert exc.value.code == 40332


@pytest.mark.asyncio
async def test_assert_identity_requires_phone_and_birth() -> None:
    async with AsyncSessionLocal() as db:
        user = await _make_user(db)
        with pytest.raises(MeetupIdentityRequiredError) as exc:
            safety_svc.assert_identity_eligible(user)
        assert exc.value.code == 40333


@pytest.mark.asyncio
async def test_accept_tos_and_ensure_access() -> None:
    async with AsyncSessionLocal() as db:
        user = await _make_user(
            db,
            birth_date=date(1995, 1, 1),
            phone_verified=True,
            gender="female",
        )
        data = await safety_svc.accept_meetup_tos(db, user=user)
        assert data["meetup_tos_accepted_at"]
        assert data["gender_preference"] == "same"
        await safety_svc.ensure_meetup_access(db, user=user)


@pytest.mark.asyncio
async def test_coach_spectator_optin_toggle() -> None:
    async with AsyncSessionLocal() as db:
        user = await _make_user(
            db,
            birth_date=date(1995, 1, 1),
            phone_verified=True,
        )
        await safety_svc.accept_meetup_tos(db, user=user)
        data = await safety_svc.update_coach_spectator_optin(db, user=user, optin=True)
        assert data["coach_spectator_optin"] is True
        data = await safety_svc.update_coach_spectator_optin(db, user=user, optin=False)
        assert data["coach_spectator_optin"] is False


@pytest.mark.asyncio
async def test_ensure_access_requires_tos() -> None:
    async with AsyncSessionLocal() as db:
        user = await _make_user(
            db,
            birth_date=date(1995, 1, 1),
            phone_verified=True,
        )
        with pytest.raises(MeetupTosRequiredError) as exc:
            await safety_svc.ensure_meetup_access(db, user=user)
        assert exc.value.code == 40334
