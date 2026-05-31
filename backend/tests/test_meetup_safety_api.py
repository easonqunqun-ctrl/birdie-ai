"""M13-09 safety API 测试."""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.user import User
from tests.meetup_test_helpers import prepare_meetup_access


@pytest.fixture
def meetup_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_MEETUP_ENABLED", True)


@pytest.mark.asyncio
async def test_verify_identity_success(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    resp = await client.post(
        "/v1/meetups/safety/verify-identity",
        json={"birth_date": "1990-05-01", "phone_code": "mock_phone_code"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["identity_eligible"] is True
    assert data["phone_verified"] is True
    assert data["can_use_meetup"] is False


@pytest.mark.asyncio
async def test_verify_identity_minor_blocked(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    resp = await client.post(
        "/v1/meetups/safety/verify-identity",
        json={"birth_date": "2015-01-01", "phone_code": "mock_phone_code"},
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 40332


@pytest.mark.asyncio
async def test_verify_identity_then_accept_tos(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    verify = await client.post(
        "/v1/meetups/safety/verify-identity",
        json={"birth_date": "1992-03-15", "phone_code": "mock_phone_code"},
        headers=auth_headers,
    )
    assert verify.status_code == 200
    accept = await client.post("/v1/meetups/safety/accept-tos", headers=auth_headers)
    assert accept.status_code == 200
    assert accept.json()["data"]["can_use_meetup"] is True


@pytest.mark.asyncio
async def test_minor_blocked_on_accept_tos(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    token = auth_headers["Authorization"].split(" ", 1)[1]
    from app.core.security import decode_access_token

    payload = decode_access_token(token)
    async with AsyncSessionLocal() as db:
        user = await db.get(User, payload["sub"])
        assert user is not None
        user.birth_date = date(2015, 1, 1)
        user.phone_verified_at = user.created_at
        await db.commit()

    resp = await client.post("/v1/meetups/safety/accept-tos", headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["code"] == 40332


@pytest.mark.asyncio
async def test_accept_tos_and_update_preference(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    await client.post("/v1/meetups/safety/mock-identity", headers=auth_headers)
    accept = await client.post("/v1/meetups/safety/accept-tos", headers=auth_headers)
    assert accept.status_code == 200
    assert accept.json()["data"]["can_use_meetup"] is True

    pref = await client.patch(
        "/v1/meetups/safety/preferences",
        json={"gender_preference": "coach_only"},
        headers=auth_headers,
    )
    assert pref.status_code == 200
    assert pref.json()["data"]["gender_preference"] == "coach_only"


@pytest.mark.asyncio
async def test_meetup_invitation_requires_tos(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    async with AsyncSessionLocal() as db:
        other = User(
            id=new_id("usr"),
            wechat_openid=f"o_{new_id('mock')}",
            nickname="other",
            invite_code=new_id("inv")[-6:].upper(),
        )
        db.add(other)
        await db.commit()
        other_id = other.id

    await client.post("/v1/meetups/safety/mock-identity", headers=auth_headers)
    blocked = await client.post(
        "/v1/meetups/invitations",
        json={"invitee_user_id": other_id},
        headers=auth_headers,
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == 40334

    await prepare_meetup_access(client, auth_headers)
    ok_resp = await client.post(
        "/v1/meetups/invitations",
        json={"invitee_user_id": other_id},
        headers=auth_headers,
    )
    assert ok_resp.status_code == 200
