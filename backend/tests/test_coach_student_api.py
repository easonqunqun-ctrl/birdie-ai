"""M8-03 · 教练-学员双向 opt-in 绑定 API 测试."""

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


APPLY_BODY = {
    "display_name": "张教练",
    "level": "china_pga",
    "bio": "十年教学经验",
    "specialties": ["short_game"],
    "service_cities": ["深圳"],
    "certifications": [{"type": "china_pga", "number": "12345"}],
    "materials": [{"type": "pga_cert", "object_key": "coach-cert/mock.pdf"}],
}


async def _login(client: AsyncClient, *, suffix: str) -> tuple[str, dict[str, str]]:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"csr_{suffix}"},
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


async def _approve_coach(
    client: AsyncClient,
    *,
    coach_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    apply = await client.post(
        "/v1/coach/profile/apply",
        json=APPLY_BODY,
        headers=coach_headers,
    )
    assert apply.status_code == 200, apply.text
    verification_id = apply.json()["data"]["latest_verification_id"]
    review = await client.post(
        f"/v1/admin/coach/verifications/{verification_id}/review",
        json={"decision": "approved", "notes": "ok"},
        headers=admin_headers,
    )
    assert review.status_code == 200, review.text


@pytest.mark.asyncio
async def test_invite_accept_end_happy_path(
    client: AsyncClient,
    coach_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _coach_id, coach_headers = await _login(client, suffix=new_id("c")[-8:])
    student_id, student_headers = await _login(client, suffix=new_id("s")[-8:])
    _admin_id, admin_headers = await _login(client, suffix=new_id("a")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", _admin_id)

    await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )
    coach_headers = await _switch_coach_role(client, coach_headers)

    invite = await client.post(
        "/v1/coach/students/invite",
        json={"student_user_id": student_id, "message": "一起练短杆"},
        headers=coach_headers,
    )
    assert invite.status_code == 200, invite.text
    relation_id = invite.json()["data"]["id"]
    assert invite.json()["data"]["status"] == "pending"

    overview = await client.get("/v1/users/me/coach", headers=student_headers)
    assert overview.status_code == 200
    assert len(overview.json()["data"]["pending"]) == 1

    accept = await client.post(
        f"/v1/users/me/coach/{relation_id}/accept",
        headers=student_headers,
    )
    assert accept.status_code == 200, accept.text
    assert accept.json()["data"]["status"] == "active"

    shared = await client.get(
        f"/v1/coach/students/{student_id}/shared-profile?field=handicap",
        headers=coach_headers,
    )
    assert shared.status_code == 403
    assert shared.json()["code"] == 40313

    vis = await client.put(
        f"/v1/users/me/coach/{relation_id}/visibility",
        json={"handicap": True},
        headers=student_headers,
    )
    assert vis.status_code == 200, vis.text

    from app.core.database import AsyncSessionLocal
    from app.schemas.user_profile_v2 import UserProfileV2Update
    from app.services import user_profile_v2_service as profile_v2_svc

    async with AsyncSessionLocal() as db:
        await profile_v2_svc.upsert_profile(
            db,
            user_id=student_id,
            payload=UserProfileV2Update(handicap_self=12, handicap_source="self"),
        )
        await db.commit()

    shared_ok = await client.get(
        f"/v1/coach/students/{student_id}/shared-profile?field=handicap",
        headers=coach_headers,
    )
    assert shared_ok.status_code == 200, shared_ok.text
    assert shared_ok.json()["data"]["value"] is not None
    assert shared_ok.json()["data"]["value"].get("handicap_self") == 12.0

    end = await client.post(
        f"/v1/users/me/coach/{relation_id}/end",
        headers=student_headers,
    )
    assert end.status_code == 200, end.text
    assert end.json()["data"]["status"] == "ended"

    after = await client.get(
        f"/v1/coach/students/{student_id}/shared-profile?field=handicap",
        headers=coach_headers,
    )
    assert after.status_code == 403
    assert after.json()["code"] == 40312


@pytest.mark.asyncio
async def test_second_coach_invite_blocked_with_40915(
    client: AsyncClient,
    coach_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_a_id, _coach_a_headers = await _login(client, suffix=new_id("ca")[-8:])
    coach_b_id, coach_b_headers = await _login(client, suffix=new_id("cb")[-8:])
    student_id, _student_headers = await _login(client, suffix=new_id("st")[-8:])
    admin_id, _admin_headers = await _login(client, suffix=new_id("ad")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", f"{coach_a_id},{coach_b_id}")

    from app.core.database import AsyncSessionLocal
    from app.services import coach_student_service as csr_svc

    async with AsyncSessionLocal() as db:
        await csr_svc.ensure_relation(
            db, coach_user_id=coach_a_id, student_user_id=student_id, status="active"
        )
        await db.commit()

    coach_b_headers = await _switch_coach_role(client, coach_b_headers)
    blocked = await client.post(
        "/v1/coach/students/invite",
        json={"student_user_id": student_id},
        headers=coach_b_headers,
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == 40915


@pytest.mark.asyncio
async def test_student_reject_invite(
    client: AsyncClient,
    coach_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_id, coach_headers = await _login(client, suffix=new_id("c2")[-8:])
    student_id, student_headers = await _login(client, suffix=new_id("s2")[-8:])
    monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", coach_id)

    coach_headers = await _switch_coach_role(client, coach_headers)
    invite = await client.post(
        "/v1/coach/students/invite",
        json={"student_user_id": student_id},
        headers=coach_headers,
    )
    assert invite.status_code == 200, invite.text
    relation_id = invite.json()["data"]["id"]

    reject = await client.post(
        f"/v1/users/me/coach/{relation_id}/reject",
        headers=student_headers,
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["data"]["status"] == "ended"


@pytest.mark.asyncio
async def test_pending_invite_expires_after_60_days(
    client: AsyncClient,
    coach_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime, timedelta

    from app.core.database import AsyncSessionLocal
    from app.models.coach import CoachStudentRelation
    from app.services import coach_student_service as csr_svc

    coach_id, coach_headers = await _login(client, suffix=new_id("ce")[-8:])
    student_id, student_headers = await _login(client, suffix=new_id("se")[-8:])
    monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", coach_id)

    coach_headers = await _switch_coach_role(client, coach_headers)
    invite = await client.post(
        "/v1/coach/students/invite",
        json={"student_user_id": student_id},
        headers=coach_headers,
    )
    assert invite.status_code == 200, invite.text
    relation_id = invite.json()["data"]["id"]

    stale_time = datetime.now(UTC) - timedelta(days=csr_svc.PENDING_INVITE_TTL_DAYS + 1)
    async with AsyncSessionLocal() as db:
        relation = await db.get(CoachStudentRelation, relation_id)
        assert relation is not None
        relation.invited_at = stale_time
        await db.commit()

    overview = await client.get("/v1/users/me/coach", headers=student_headers)
    assert overview.status_code == 200
    assert overview.json()["data"]["pending"] == []
