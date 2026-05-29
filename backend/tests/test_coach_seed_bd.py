"""M8-10 · 种子教练 BD：level=seed + 一年权益开通."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.security import new_id


@pytest.fixture
def coach_bd_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", True)


async def _login(client: AsyncClient, *, suffix: str) -> tuple[str, dict[str, str]]:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"seed_bd_{suffix}"},
    )
    assert login.status_code == 200, login.text
    user_id = login.json()["data"]["user"]["id"]
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    return user_id, headers


async def _approve_coach(
    client: AsyncClient,
    *,
    coach_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> str:
    apply = await client.post(
        "/v1/coach/profile/apply",
        json={
            "display_name": "种子教练",
            "level": "china_pga",
            "materials": [{"type": "cert", "object_key": "k1"}],
        },
        headers=coach_headers,
    )
    assert apply.status_code == 200, apply.text
    coach_id = apply.json()["data"]["user_id"]
    vid = apply.json()["data"]["latest_verification_id"]
    review = await client.post(
        f"/v1/admin/coach/verifications/{vid}/review",
        json={"decision": "approved"},
        headers=admin_headers,
    )
    assert review.status_code == 200, review.text
    return coach_id


@pytest.mark.asyncio
async def test_admin_marks_seed_and_grants_year_premium(
    client: AsyncClient,
    coach_bd_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_id, coach_headers = await _login(client, suffix=new_id("c")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("a")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    coach_id = await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )

    mark = await client.patch(
        f"/v1/admin/coach/profiles/{coach_id}/level",
        json={"level": "seed"},
        headers=admin_headers,
    )
    assert mark.status_code == 200, mark.text
    assert mark.json()["data"]["level"] == "seed"

    me_before = await client.get("/v1/users/me", headers=coach_headers)
    assert me_before.json()["data"]["membership_type"] == "free"

    grant = await client.post(
        f"/v1/admin/coach/profiles/{coach_id}/grant-seed-premium",
        json={"valid_days": 365},
        headers=admin_headers,
    )
    assert grant.status_code == 200, grant.text
    assert grant.json()["data"]["membership_type"] == "yearly"
    assert grant.json()["data"]["granted_days"] == 365

    me_after = await client.get("/v1/users/me", headers=coach_headers)
    assert me_after.json()["data"]["membership_type"] == "yearly"
    assert me_after.json()["data"]["is_member"] is True
    assert me_after.json()["data"]["quota"]["analysis_remaining"] == -1


@pytest.mark.asyncio
async def test_grant_rejects_non_seed_coach(
    client: AsyncClient,
    coach_bd_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_id, coach_headers = await _login(client, suffix=new_id("c2")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("a2")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    coach_id = await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )

    grant = await client.post(
        f"/v1/admin/coach/profiles/{coach_id}/grant-seed-premium",
        json={"valid_days": 365},
        headers=admin_headers,
    )
    assert grant.status_code == 400
    assert grant.json()["code"] == 40001


@pytest.mark.asyncio
async def test_list_seed_profiles(
    client: AsyncClient,
    coach_bd_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_id, coach_headers = await _login(client, suffix=new_id("c3")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("a3")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)

    coach_id = await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )
    await client.patch(
        f"/v1/admin/coach/profiles/{coach_id}/level",
        json={"level": "seed"},
        headers=admin_headers,
    )

    listed = await client.get(
        "/v1/admin/coach/profiles?level=seed",
        headers=admin_headers,
    )
    assert listed.status_code == 200, listed.text
    ids = [item["user_id"] for item in listed.json()["data"]["items"]]
    assert coach_id in ids
