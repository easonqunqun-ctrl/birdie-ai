"""M13-10 · 教练旁观学员约球 API 测试."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.user import User
from app.services import coach_student_service as csr_svc
from app.services.coach_spectator_service import REDACTED_PEER_USER_ID
from tests.meetup_test_helpers import prepare_meetup_access


@pytest.fixture
def meetup_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_MEETUP_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", True)


@pytest.fixture
def meetup_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_MEETUP_ENABLED", False)


async def _make_user(*, nickname: str = "u") -> User:
    async with AsyncSessionLocal() as db:
        u = User(
            id=new_id("usr"),
            wechat_openid=f"o_{new_id('mock')}",
            nickname=nickname,
            invite_code=new_id("inv")[-6:].upper(),
            birth_date=date(1995, 1, 1),
            phone_verified_at=datetime.now(UTC),
        )
        db.add(u)
        await db.commit()
        await db.refresh(u)
        return u


async def _login(client: AsyncClient, *, code_suffix: str) -> tuple[str, dict[str, str]]:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"coach_spec_{code_suffix}"},
    )
    assert login.status_code == 200, login.text
    user_id = login.json()["data"]["user"]["id"]
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    return user_id, headers


async def _switch_coach_role(
    client: AsyncClient, headers: dict[str, str]
) -> dict[str, str]:
    resp = await client.post(
        "/v1/auth/role-switch",
        json={"role": "coach"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


@pytest.mark.asyncio
async def test_coach_student_meetups_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_disabled: None,
) -> None:
    resp = await client.get(
        "/v1/coach/students/usr_x/meetups",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_coach_spectator_happy_path(
    client: AsyncClient,
    meetup_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_id, coach_headers = await _login(client, code_suffix=new_id("c")[-8:])
    student_id, student_headers = await _login(client, code_suffix=new_id("s")[-8:])
    peer = await _make_user(nickname="peer")

    monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", coach_id)

    async with AsyncSessionLocal() as db:
        await csr_svc.ensure_relation(
            db, coach_user_id=coach_id, student_user_id=student_id
        )
        await db.commit()

    await prepare_meetup_access(client, student_headers)
    optin = await client.patch(
        "/v1/meetups/safety/spectator-optin",
        json={"coach_spectator_optin": True},
        headers=student_headers,
    )
    assert optin.status_code == 200, optin.text

    create = await client.post(
        "/v1/meetups/invitations",
        json={"invitee_user_id": peer.id, "message": "练球"},
        headers=student_headers,
    )
    assert create.status_code == 200, create.text
    inv_id = create.json()["data"]["id"]

    coach_headers = await _switch_coach_role(client, coach_headers)

    list_resp = await client.get(
        f"/v1/coach/students/{student_id}/meetups",
        headers=coach_headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    data = list_resp.json()["data"]
    assert data["student_user_id"] == student_id
    assert data["total"] >= 1
    item = next(i for i in data["items"] if i["id"] == inv_id)
    assert item["student_role"] == "inviter"
    assert item["peer_user_id"] == REDACTED_PEER_USER_ID
    assert item["peer_redacted"] is True
    assert "contact_payload" not in item


@pytest.mark.asyncio
async def test_coach_spectator_rejects_without_optin(
    client: AsyncClient,
    meetup_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_id, coach_headers = await _login(client, code_suffix=new_id("c2")[-8:])
    student_id, student_headers = await _login(client, code_suffix=new_id("s2")[-8:])

    monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", coach_id)

    async with AsyncSessionLocal() as db:
        await csr_svc.ensure_relation(
            db, coach_user_id=coach_id, student_user_id=student_id
        )
        await db.commit()

    await prepare_meetup_access(client, student_headers)

    coach_headers = await _switch_coach_role(client, coach_headers)

    resp = await client.get(
        f"/v1/coach/students/{student_id}/meetups",
        headers=coach_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 40336


@pytest.mark.asyncio
async def test_coach_spectator_optin_revoke(
    client: AsyncClient,
    meetup_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_id, coach_headers = await _login(client, code_suffix=new_id("c3")[-8:])
    student_id, student_headers = await _login(client, code_suffix=new_id("s3")[-8:])

    monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", coach_id)

    async with AsyncSessionLocal() as db:
        await csr_svc.ensure_relation(
            db, coach_user_id=coach_id, student_user_id=student_id
        )
        await db.commit()

    await prepare_meetup_access(client, student_headers)
    await client.patch(
        "/v1/meetups/safety/spectator-optin",
        json={"coach_spectator_optin": True},
        headers=student_headers,
    )

    coach_headers = await _switch_coach_role(client, coach_headers)

    revoke = await client.patch(
        "/v1/meetups/safety/spectator-optin",
        json={"coach_spectator_optin": False},
        headers=student_headers,
    )
    assert revoke.status_code == 200
    assert revoke.json()["data"]["coach_spectator_optin"] is False

    resp = await client.get(
        f"/v1/coach/students/{student_id}/meetups",
        headers=coach_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 40336


@pytest.mark.asyncio
async def test_coach_spectator_requires_relation(
    client: AsyncClient,
    meetup_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_id, coach_headers = await _login(client, code_suffix=new_id("c4")[-8:])
    student = await _make_user()

    monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", coach_id)

    resp = await client.get(
        f"/v1/coach/students/{student.id}/meetups",
        headers=coach_headers,
    )
    assert resp.status_code == 404
