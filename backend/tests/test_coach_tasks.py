"""M8-05 · 教练作业派发 API 测试."""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.training import Drill
from app.services.training_service import week_bounds

APPLY_BODY = {
    "display_name": "作业教练",
    "level": "china_pga",
    "bio": "十年教学经验",
    "specialties": ["short_game"],
    "service_cities": ["深圳"],
    "certifications": [{"type": "china_pga", "number": "12345"}],
    "materials": [{"type": "pga_cert", "object_key": "coach-cert/mock.pdf"}],
}


@pytest.fixture
def coach_tasks_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_TASKS_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", True)


@pytest.fixture
def coach_tasks_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_TASKS_ENABLED", False)


async def _login(client: AsyncClient, *, suffix: str) -> tuple[str, dict[str, str]]:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"coach_task_{suffix}"},
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


async def _bind_active_student(
    client: AsyncClient,
    *,
    coach_headers: dict[str, str],
    student_headers: dict[str, str],
    student_id: str,
) -> None:
    invite = await client.post(
        "/v1/coach/students/invite",
        json={"student_user_id": student_id, "message": "一起练球"},
        headers=coach_headers,
    )
    assert invite.status_code == 200, invite.text
    relation_id = invite.json()["data"]["id"]
    accept = await client.post(
        f"/v1/users/me/coach/invitations/{relation_id}/accept",
        headers=student_headers,
    )
    assert accept.status_code == 200, accept.text


async def _setup_coach_student_pair(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, str], dict[str, str], str]:
    _coach_id, coach_headers = await _login(client, suffix=new_id("c")[-8:])
    student_id, student_headers = await _login(client, suffix=new_id("s")[-8:])
    _admin_id, admin_headers = await _login(client, suffix=new_id("a")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", _admin_id)

    await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )
    coach_headers = await _switch_coach_role(client, coach_headers)
    await _bind_active_student(
        client,
        coach_headers=coach_headers,
        student_headers=student_headers,
        student_id=student_id,
    )
    return coach_headers, student_headers, student_id


async def _pick_drill_id() -> str:
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            select(Drill.id).where(Drill.is_active.is_(True)).limit(1)
        )
        drill_id = row.scalar_one_or_none()
        if drill_id is None:
            pytest.skip("no active drills seeded")
        return drill_id


@pytest.mark.asyncio
async def test_coach_task_assign_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    coach_tasks_disabled: None,
) -> None:
    resp = await client.post(
        "/v1/coach/tasks/assign",
        headers=auth_headers,
        json={
            "student_user_id": "usr_x",
            "source_type": "drill",
            "drill_id": "drill_half_swing",
            "target_week": date.today().isoformat(),
            "target_count": 1,
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_coach_task_assign_happy_path(
    client: AsyncClient,
    coach_tasks_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_headers, student_headers, student_id = await _setup_coach_student_pair(
        client, monkeypatch
    )
    drill_id = await _pick_drill_id()
    monday, _ = week_bounds(date.today())

    assign = await client.post(
        "/v1/coach/tasks/assign",
        headers=coach_headers,
        json={
            "student_user_id": student_id,
            "source_type": "drill",
            "drill_id": drill_id,
            "target_week": monday.isoformat(),
            "target_count": 3,
            "coach_note": "本周重点练这个",
        },
    )
    assert assign.status_code == 200, assign.text
    data = assign.json()["data"]
    assert data["drill_id"] == drill_id
    assert data["target_count"] == 3
    assert data["training_task_id"]

    plan = await client.get(
        "/v1/users/me/training-plan/current",
        headers=student_headers,
    )
    assert plan.status_code == 200
    tasks = plan.json()["data"]["tasks"]
    coach_tasks = [t for t in tasks if t.get("task_kind") == "coach_assigned"]
    assert len(coach_tasks) == 1
    assert coach_tasks[0]["coach_target_count"] == 3
    assert coach_tasks[0]["coach_note"] == "本周重点练这个"

    complete = await client.post(
        f"/v1/training-plan/tasks/{coach_tasks[0]['id']}/complete",
        headers=student_headers,
        json={},
    )
    assert complete.status_code == 200

    listed = await client.get(
        f"/v1/coach/tasks?student_id={student_id}",
        headers=coach_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["status"] == "done"


@pytest.mark.asyncio
async def test_coach_task_requires_active_relation(
    client: AsyncClient,
    coach_tasks_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _coach_id, coach_headers = await _login(client, suffix=new_id("c")[-8:])
    _admin_id, admin_headers = await _login(client, suffix=new_id("a")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", _admin_id)
    await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )
    coach_headers = await _switch_coach_role(client, coach_headers)

    stranger_id, _ = await _login(client, suffix=new_id("x")[-8:])
    drill_id = await _pick_drill_id()
    monday, _ = week_bounds(date.today())

    resp = await client.post(
        "/v1/coach/tasks/assign",
        headers=coach_headers,
        json={
            "student_user_id": stranger_id,
            "source_type": "drill",
            "drill_id": drill_id,
            "target_week": monday.isoformat(),
            "target_count": 1,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 40312
