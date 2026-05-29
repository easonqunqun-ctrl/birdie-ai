"""M8-08 · 教练 UGC 内容审核测试."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.services.content_safety_service import (
    MOCK_MANUAL_REVIEW_TOKEN,
    MOCK_PROVIDER_FAIL_TOKEN,
    MOCK_REJECT_TOKEN,
    moderate_text,
)

APPLY_BODY = {
    "display_name": "审核教练",
    "level": "china_pga",
    "bio": "十年教学经验",
    "specialties": ["short_game"],
    "service_cities": ["深圳"],
    "certifications": [{"type": "china_pga", "number": "12345"}],
    "materials": [{"type": "pga_cert", "object_key": "coach-cert/mock.pdf"}],
}


@pytest.fixture
def moderation_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_CONTENT_MODERATION_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_COACH_ANNOTATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_COACH_TASKS_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", True)


async def _login(client: AsyncClient, *, suffix: str) -> tuple[str, dict[str, str]]:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"mod_{suffix}"},
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
        f"/v1/users/me/coach/{relation_id}/accept",
        headers=student_headers,
    )
    assert accept.status_code == 200, accept.text


async def _seed_analysis(*, user_id: str) -> str:
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


@pytest.mark.asyncio
async def test_moderation_mock_tokens() -> None:
    approved = await moderate_text("正常批注")
    assert approved.decision.value == "approved"
    rejected = await moderate_text(f"违规 {MOCK_REJECT_TOKEN}")
    assert rejected.decision.value == "rejected"
    review = await moderate_text(f"边缘 {MOCK_MANUAL_REVIEW_TOKEN}")
    assert review.decision.value == "manual_review"
    pending = await moderate_text(f"故障 {MOCK_PROVIDER_FAIL_TOKEN}")
    assert pending.decision.value == "pending"
    assert pending.provider_error is True


@pytest.mark.asyncio
async def test_text_annotation_rejected_hidden_from_student(
    client: AsyncClient,
    moderation_enabled: None,
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
    await _bind_active_student(
        client,
        coach_headers=coach_headers,
        student_headers=student_headers,
        student_id=student_id,
    )
    analysis_id = await _seed_analysis(user_id=student_id)

    create = await client.post(
        f"/v1/coach/analyses/{analysis_id}/annotations",
        json={
            "annotation_type": "text",
            "text_content": f"不当内容 {MOCK_REJECT_TOKEN}",
        },
        headers=coach_headers,
    )
    assert create.status_code == 200, create.text
    assert create.json()["data"]["audit_status"] == "rejected"
    assert create.json()["data"]["is_visible"] is False

    student_list = await client.get(
        f"/v1/analyses/{analysis_id}/coach-annotations",
        headers=student_headers,
    )
    assert student_list.status_code == 200, student_list.text
    assert student_list.json()["data"] == []


@pytest.mark.asyncio
async def test_manual_review_admin_approve(
    client: AsyncClient,
    moderation_enabled: None,
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
    await _bind_active_student(
        client,
        coach_headers=coach_headers,
        student_headers=student_headers,
        student_id=student_id,
    )
    analysis_id = await _seed_analysis(user_id=student_id)

    create = await client.post(
        f"/v1/coach/analyses/{analysis_id}/annotations",
        json={
            "annotation_type": "text",
            "text_content": f"需复核 {MOCK_MANUAL_REVIEW_TOKEN}",
        },
        headers=coach_headers,
    )
    assert create.status_code == 200, create.text
    assert create.json()["data"]["audit_status"] == "manual_review"

    queue = await client.get("/v1/admin/moderation/queue", headers=admin_headers)
    assert queue.status_code == 200, queue.text
    items = queue.json()["data"]["items"]
    assert items
    queue_id = items[0]["id"]

    review = await client.post(
        f"/v1/admin/moderation/queue/{queue_id}/review",
        json={"action": "approve", "note": "人工通过"},
        headers=admin_headers,
    )
    assert review.status_code == 200, review.text

    student_list = await client.get(
        f"/v1/analyses/{analysis_id}/coach-annotations",
        headers=student_headers,
    )
    assert student_list.status_code == 200, student_list.text
    assert len(student_list.json()["data"]) == 1


@pytest.mark.asyncio
async def test_fail_safe_pending_not_visible(
    client: AsyncClient,
    moderation_enabled: None,
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
    await _bind_active_student(
        client,
        coach_headers=coach_headers,
        student_headers=student_headers,
        student_id=student_id,
    )
    analysis_id = await _seed_analysis(user_id=student_id)

    create = await client.post(
        f"/v1/coach/analyses/{analysis_id}/annotations",
        json={
            "annotation_type": "text",
            "text_content": f"供应商故障 {MOCK_PROVIDER_FAIL_TOKEN}",
        },
        headers=coach_headers,
    )
    assert create.status_code == 200, create.text
    assert create.json()["data"]["audit_status"] == "pending"
    assert create.json()["data"]["is_visible"] is False

    student_list = await client.get(
        f"/v1/analyses/{analysis_id}/coach-annotations",
        headers=student_headers,
    )
    assert student_list.json()["data"] == []
