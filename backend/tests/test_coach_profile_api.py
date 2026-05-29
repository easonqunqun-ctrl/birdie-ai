"""M8-01 · 教练档案 / 资质审核 API 测试."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.security import new_id


@pytest.fixture
def coach_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", True)


@pytest.fixture
def coach_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", False)


async def _login(client: AsyncClient, *, suffix: str) -> tuple[str, dict[str, str]]:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"coach_prof_{suffix}"},
    )
    assert login.status_code == 200, login.text
    user_id = login.json()["data"]["user"]["id"]
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    return user_id, headers


APPLY_BODY = {
    "display_name": "张教练",
    "level": "china_pga",
    "bio": "十年教学经验",
    "specialties": ["short_game"],
    "service_cities": ["深圳"],
    "certifications": [{"type": "china_pga", "number": "12345"}],
    "materials": [{"type": "pga_cert", "object_key": "coach-cert/mock.pdf"}],
}


@pytest.mark.asyncio
async def test_apply_coach_profile_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    coach_disabled: None,
) -> None:
    resp = await client.post(
        "/v1/coach/profile/apply",
        json=APPLY_BODY,
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_coach_apply_and_admin_review_happy_path(
    client: AsyncClient,
    coach_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _applicant_id, applicant_headers = await _login(client, suffix=new_id("a")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("adm")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    apply = await client.post(
        "/v1/coach/profile/apply",
        json=APPLY_BODY,
        headers=applicant_headers,
    )
    assert apply.status_code == 200, apply.text
    data = apply.json()["data"]
    assert data["status"] == "pending"
    verification_id = data["latest_verification_id"]
    assert verification_id

    me = await client.get("/v1/coach/profile/me", headers=applicant_headers)
    assert me.status_code == 200
    assert me.json()["data"]["display_name"] == "张教练"

    pending = await client.get(
        "/v1/admin/coach/verifications?status=pending",
        headers=admin_headers,
    )
    assert pending.status_code == 200
    ids = {i["id"] for i in pending.json()["data"]["items"]}
    assert verification_id in ids

    review = await client.post(
        f"/v1/admin/coach/verifications/{verification_id}/review",
        json={"decision": "approved", "notes": "资质齐全"},
        headers=admin_headers,
    )
    assert review.status_code == 200, review.text
    assert review.json()["data"]["review_status"] == "approved"

    profile = await client.get("/v1/coach/profile/me", headers=applicant_headers)
    assert profile.json()["data"]["status"] == "active"

    user_me = await client.get("/v1/users/me", headers=applicant_headers)
    assert user_me.json()["data"]["is_active_coach"] is True
    assert user_me.json()["data"]["coach_profile"]["status"] == "active"


@pytest.mark.asyncio
async def test_reapply_after_reject(
    client: AsyncClient,
    coach_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _applicant_id, applicant_headers = await _login(client, suffix=new_id("r")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("rad")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    first = await client.post(
        "/v1/coach/profile/apply",
        json=APPLY_BODY,
        headers=applicant_headers,
    )
    vid = first.json()["data"]["latest_verification_id"]

    await client.post(
        f"/v1/admin/coach/verifications/{vid}/review",
        json={"decision": "rejected", "notes": "材料不清"},
        headers=admin_headers,
    )

    second = await client.post(
        "/v1/coach/profile/apply",
        json={**APPLY_BODY, "display_name": "张教练二"},
        headers=applicant_headers,
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["status"] == "pending"
    assert second.json()["data"]["latest_verification_id"] != vid


@pytest.mark.asyncio
async def test_admin_forbidden_for_non_admin(
    client: AsyncClient,
    coach_enabled: None,
) -> None:
    _, headers = await _login(client, suffix=new_id("x")[-8:])
    resp = await client.get(
        "/v1/admin/coach/verifications",
        headers=headers,
    )
    assert resp.status_code == 403
