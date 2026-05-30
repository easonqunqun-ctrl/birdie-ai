"""M8-04 / M12-09 · 教练批注 API + service 测试."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.services import pro_library_service as pro_svc

APPLY_BODY = {
    "display_name": "批注教练",
    "level": "china_pga",
    "bio": "十年教学经验",
    "specialties": ["short_game"],
    "service_cities": ["深圳"],
    "certifications": [{"type": "china_pga", "number": "12345"}],
    "materials": [{"type": "pga_cert", "object_key": "coach-cert/mock.pdf"}],
}


@pytest.fixture
def coach_ann_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_ANNOTATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_PROS_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", True)


@pytest.fixture
def coach_ann_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_ANNOTATIONS_ENABLED", False)


async def _login(client: AsyncClient, *, suffix: str) -> tuple[str, dict[str, str]]:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"coach_ann_{suffix}"},
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


async def _seed_completed_analysis(*, user_id: str) -> str:
    analysis_id = new_id("ana")
    async with AsyncSessionLocal() as db:
        db.add(
            SwingAnalysis(
                id=analysis_id,
                user_id=user_id,
                status="completed",
                stage="completed",
                stage_progress=100,
                camera_angle="face_on",
                club_type="iron_7",
                video_url="https://x/v.mp4",
                video_duration=8.0,
                overall_score=80,
                created_at=datetime.now(UTC),
                analyzed_at=datetime.now(UTC),
            )
        )
        await db.commit()
    return analysis_id


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


@pytest.mark.asyncio
async def test_coach_annotation_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    coach_ann_disabled: None,
) -> None:
    resp = await client.get(
        "/v1/analyses/ana_x/coach-annotations",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_coach_annotation_requires_active_relation(
    client: AsyncClient,
    coach_ann_enabled: None,
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
    analysis_id = await _seed_completed_analysis(user_id=stranger_id)

    create = await client.post(
        f"/v1/coach/analyses/{analysis_id}/annotations",
        headers=coach_headers,
        json={"annotation_type": "text", "text_content": "注意送杆"},
    )
    assert create.status_code == 403
    assert create.json()["code"] == 40312


@pytest.mark.asyncio
async def test_coach_text_annotation_happy_path(
    client: AsyncClient,
    coach_ann_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_headers, student_headers, student_id = await _setup_coach_student_pair(
        client, monkeypatch
    )
    analysis_id = await _seed_completed_analysis(user_id=student_id)

    create = await client.post(
        f"/v1/coach/analyses/{analysis_id}/annotations",
        headers=coach_headers,
        json={"annotation_type": "text", "text_content": "送杆再完整一些"},
    )
    assert create.status_code == 200, create.text
    assert create.json()["data"]["annotation_type"] == "text"
    assert create.json()["data"]["text_content"] == "送杆再完整一些"

    student_list = await client.get(
        f"/v1/analyses/{analysis_id}/coach-annotations",
        headers=student_headers,
    )
    assert student_list.status_code == 200
    assert len(student_list.json()["data"]) == 1
    assert student_list.json()["data"][0]["text_content"] == "送杆再完整一些"


@pytest.mark.asyncio
async def test_coach_video_ref_happy_path(
    client: AsyncClient,
    coach_ann_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_headers, student_headers, student_id = await _setup_coach_student_pair(
        client, monkeypatch
    )
    analysis_id = await _seed_completed_analysis(user_id=student_id)
    async with AsyncSessionLocal() as db:
        players = await pro_svc.seed_initial_pros(db)
        clips = await pro_svc.list_published_clips(db, player_id=players[0].id)
        await db.commit()
        clip_id = clips[0].id

    create = await client.post(
        f"/v1/coach/analyses/{analysis_id}/annotations",
        headers=coach_headers,
        json={"annotation_type": "video_ref", "pro_clip_id": clip_id},
    )
    assert create.status_code == 200
    assert create.json()["data"]["pro_clip_id"] == clip_id
    assert create.json()["data"]["clip"]["id"] == clip_id

    student_list = await client.get(
        f"/v1/analyses/{analysis_id}/coach-annotations",
        headers=student_headers,
    )
    assert student_list.status_code == 200
    assert len(student_list.json()["data"]) == 1
    assert student_list.json()["data"][0]["player"]["name"]

    me = await client.get("/v1/users/me", headers=coach_headers)
    assert me.json()["data"]["can_coach_annotate"] is False
    assert me.json()["data"]["is_active_coach"] is True


@pytest.mark.asyncio
async def test_coach_delete_annotation(
    client: AsyncClient,
    coach_ann_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coach_headers, student_headers, student_id = await _setup_coach_student_pair(
        client, monkeypatch
    )
    analysis_id = await _seed_completed_analysis(user_id=student_id)

    create = await client.post(
        f"/v1/coach/analyses/{analysis_id}/annotations",
        headers=coach_headers,
        json={"annotation_type": "text", "text_content": "待删除"},
    )
    assert create.status_code == 200
    ann_id = create.json()["data"]["id"]

    deleted = await client.delete(
        f"/v1/coach/annotations/{ann_id}",
        headers=coach_headers,
    )
    assert deleted.status_code == 200

    student_list = await client.get(
        f"/v1/analyses/{analysis_id}/coach-annotations",
        headers=student_headers,
    )
    assert student_list.status_code == 200
    assert student_list.json()["data"] == []
