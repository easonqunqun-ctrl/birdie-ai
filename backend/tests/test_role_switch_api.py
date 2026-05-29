"""M8-02 · 教练身份切换 API 测试."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.services import coach_student_service as csr_svc
from tests.meetup_test_helpers import prepare_meetup_access


@pytest.fixture
def coach_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_MEETUP_ENABLED", True)


async def _login(client: AsyncClient, *, suffix: str) -> tuple[str, dict[str, str]]:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"role_sw_{suffix}"},
    )
    assert login.status_code == 200, login.text
    user_id = login.json()["data"]["user"]["id"]
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    return user_id, headers


async def _approve_coach(
    client: AsyncClient,
    *,
    applicant_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    apply = await client.post(
        "/v1/coach/profile/apply",
        json={
            "display_name": "教练A",
            "level": "china_pga",
            "materials": [{"type": "cert", "object_key": "k1"}],
        },
        headers=applicant_headers,
    )
    assert apply.status_code == 200, apply.text
    vid = apply.json()["data"]["latest_verification_id"]
    review = await client.post(
        f"/v1/admin/coach/verifications/{vid}/review",
        json={"decision": "approved"},
        headers=admin_headers,
    )
    assert review.status_code == 200, review.text


@pytest.mark.asyncio
async def test_role_switch_to_coach_after_approval(
    client: AsyncClient,
    coach_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_id, coach_headers = await _login(client, suffix=new_id("c")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("a")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    await _approve_coach(client, applicant_headers=coach_headers, admin_headers=admin_headers)

    switch = await client.post(
        "/v1/auth/role-switch",
        json={"role": "coach"},
        headers=coach_headers,
    )
    assert switch.status_code == 200, switch.text
    data = switch.json()["data"]
    assert data["role"] == "coach"
    coach_headers = {"Authorization": f"Bearer {data['token']}"}

    student_id, student_headers = await _login(client, suffix=new_id("s")[-8:])
    async with AsyncSessionLocal() as db:
        await csr_svc.ensure_relation(db, coach_user_id=coach_id, student_user_id=student_id)
        await db.commit()
    await prepare_meetup_access(client, student_headers)
    await client.patch(
        "/v1/meetups/safety/spectator-optin",
        json={"coach_spectator_optin": True},
        headers=student_headers,
    )

    resp = await client.get(
        f"/v1/coach/students/{student_id}/meetups",
        headers=coach_headers,
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_role_switch_rejects_non_coach(
    client: AsyncClient,
    coach_enabled: None,
) -> None:
    _, headers = await _login(client, suffix=new_id("x")[-8:])
    resp = await client.post(
        "/v1/auth/role-switch",
        json={"role": "coach"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 40320


@pytest.mark.asyncio
async def test_coach_api_requires_jwt_coach_role(
    client: AsyncClient,
    coach_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_id, coach_headers = await _login(client, suffix=new_id("c2")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("a2")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", coach_id)

    await _approve_coach(client, applicant_headers=coach_headers, admin_headers=admin_headers)

    student_id, _ = await _login(client, suffix=new_id("s2")[-8:])
    async with AsyncSessionLocal() as db:
        await csr_svc.ensure_relation(db, coach_user_id=coach_id, student_user_id=student_id)
        await db.commit()

    resp = await client.get(
        f"/v1/coach/students/{student_id}/meetups",
        headers=coach_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 40310


@pytest.mark.asyncio
async def test_role_switch_back_to_user(
    client: AsyncClient,
    coach_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _coach_id, coach_headers = await _login(client, suffix=new_id("c3")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("a3")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    await _approve_coach(client, applicant_headers=coach_headers, admin_headers=admin_headers)

    to_coach = await client.post(
        "/v1/auth/role-switch",
        json={"role": "coach"},
        headers=coach_headers,
    )
    coach_headers = {"Authorization": f"Bearer {to_coach.json()['data']['token']}"}

    to_user = await client.post(
        "/v1/auth/role-switch",
        json={"role": "user"},
        headers=coach_headers,
    )
    assert to_user.status_code == 200
    assert to_user.json()["data"]["role"] == "user"
