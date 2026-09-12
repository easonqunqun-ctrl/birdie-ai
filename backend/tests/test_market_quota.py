"""各市场前 100 名各 100 次欢迎包."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.services import market_service, quota_service
from app.services.market_service import classify_market


def test_classify_market_force_cn() -> None:
    assert classify_market(force_cn=True, header="intl", accept_language="en") == "cn"


def test_classify_market_header() -> None:
    assert classify_market(header="intl") == "intl"
    assert classify_market(header="cn", accept_language="en-US") == "cn"


def test_classify_market_accept_language() -> None:
    assert classify_market(accept_language="en-US,en;q=0.9") == "intl"
    assert classify_market(accept_language="zh-CN") == "cn"
    assert classify_market() == "cn"


def test_offer_standard_without_grant() -> None:
    user = User(id="usr_cn", invite_code="CNFREE01", market="cn")
    offer = market_service.offer_for(user)
    assert offer.policy == "standard"
    assert market_service.is_cn_free(user) is False


def test_offer_welcome() -> None:
    user = User(
        id="usr_in",
        invite_code="INTL0001",
        market="intl",
        intl_welcome_granted=True,
        intl_welcome_remaining=47,
    )
    offer = market_service.offer_for(user)
    assert offer.policy == "welcome"
    assert offer.intl_welcome_remaining == 47


@pytest.mark.asyncio
async def test_welcome_quota_and_consume(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "QUOTA_MODE", "strict")
    monkeypatch.setattr(settings, "WELCOME_ANALYSES", 100)

    me = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    user_id = me["id"]

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        assert user is not None
        user.market = "cn"
        user.intl_welcome_granted = True
        user.intl_welcome_remaining = 2
        await db.commit()

    me2 = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me2["market_offer"]["policy"] == "welcome"
    assert me2["quota"]["analysis_remaining"] == 2
    assert me2["quota"]["analysis_total"] == 100
    assert me2["quota"]["analysis_reset_at"] is None

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        await quota_service.consume_analysis_quota(db, user)
        await db.commit()
        await db.refresh(user)
        assert user.intl_welcome_remaining == 1
        await quota_service.get_or_create_analysis_quota(db, user)
        refunded = await quota_service.refund_analysis_quota_by_user_month(
            db,
            user_id=user_id,
            quota_month=quota_service._now_month_str(),
        )
        await db.commit()
        await db.refresh(user)
        assert refunded is True
        assert user.intl_welcome_remaining == 2


@pytest.mark.asyncio
async def test_welcome_cap_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "WELCOME_USER_CAP", 0)
    monkeypatch.setattr(settings, "WELCOME_ANALYSES", 100)
    user = User(id="usr_cap", invite_code="CAP00001", market="cn")
    async with AsyncSessionLocal() as db:
        await market_service._try_grant_welcome(db, user, redis=None)
    assert user.intl_welcome_granted is False
