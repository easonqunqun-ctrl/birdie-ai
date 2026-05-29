"""M8-07 · 教练教学报告 API 测试."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.integrations.llm import FakeLLMClient
from app.models.analysis import AnalysisIssue, SwingAnalysis
from app.services.llm.coach_recap_prompt import summary_passes_quality_gate
from tests.fakes import FakeMinioStorage

APPLY_BODY = {
    "display_name": "报告教练",
    "level": "china_pga",
    "bio": "十年教学经验",
    "specialties": ["short_game"],
    "service_cities": ["深圳"],
    "certifications": [{"type": "china_pga", "number": "12345"}],
    "materials": [{"type": "pga_cert", "object_key": "coach-cert/mock.pdf"}],
}


@pytest.fixture
def recap_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_RECAP_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", True)


@pytest.fixture
def recap_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_RECAP_ENABLED", False)



async def _login(client: AsyncClient, *, suffix: str) -> tuple[str, dict[str, str]]:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"recap_{suffix}"},
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


async def _seed_analysis_with_issue(*, user_id: str, student_name: str) -> str:
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
        db.add(
            AnalysisIssue(
                id=new_id("iss"),
                analysis_id=analysis_id,
                issue_type="early_extension",
                name="Early Extension",
                severity="medium",
                description=f"{student_name} 下杆时过早伸展",
                sort_order=0,
            )
        )
        await db.commit()
    return analysis_id


def test_summary_quality_gate() -> None:
    from app.services.llm.coach_recap_prompt import RecapIssueBrief, RecapStudentContext

    ctx = RecapStudentContext(
        student_user_id="usr_1",
        display_name="张三",
        analysis_id="ana_1",
        overall_score=80,
        club_type="iron_7",
        issues=[
            RecapIssueBrief(
                name="Early Extension",
                issue_type="early_extension",
                severity="medium",
                score=62,
            )
        ],
    )
    good = "## 课程概述\n## 张三 的本次表现\nEarly Extension 需要关注。"
    bad = "## 课程概述\n整体不错。"
    assert summary_passes_quality_gate(good, [ctx]) is True
    assert summary_passes_quality_gate(bad, [ctx]) is False


@pytest.mark.asyncio
async def test_recap_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    recap_disabled: None,
) -> None:
    resp = await client.post(
        "/v1/coach/sessions/recap",
        json={
            "session_date": date.today().isoformat(),
            "student_ids": ["usr_x"],
            "analysis_ids": ["ana_x"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_recap_create_export_and_list(
    client: AsyncClient,
    fake_minio: FakeMinioStorage,
    use_fake_llm: FakeLLMClient,
    recap_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.models.user import User

    _coach_id, coach_headers = await _login(client, suffix=new_id("c")[-8:])
    student_id, student_headers = await _login(client, suffix=new_id("s")[-8:])
    _admin_id, admin_headers = await _login(client, suffix=new_id("a")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", _admin_id)

    async with AsyncSessionLocal() as db:
        student = await db.get(User, student_id)
        assert student is not None
        student.nickname = "学员A"
        await db.commit()

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
    analysis_id = await _seed_analysis_with_issue(user_id=student_id, student_name="学员A")

    use_fake_llm.set_reply(
        "## 课程概述\n"
        "## 学员A 的本次表现\n"
        "Early Extension 在下杆阶段明显，建议加强髋部稳定。\n"
        "## 下次课程建议\n"
        "复习 early_extension 对应 drill。"
    )

    create = await client.post(
        "/v1/coach/sessions/recap",
        json={
            "session_date": date.today().isoformat(),
            "student_ids": [student_id],
            "analysis_ids": [analysis_id],
            "coach_manual_notes": "下节课重点练节奏",
        },
        headers=coach_headers,
    )
    assert create.status_code == 200, create.text
    body = create.json()["data"]
    recap_id = body["recap_id"]
    assert "Early Extension" in body["ai_summary"]
    assert body["status"] == "finalized"

    export = await client.post(
        f"/v1/coach/sessions/{recap_id}/export-pdf",
        headers=coach_headers,
    )
    assert export.status_code == 200, export.text
    pdf_body = export.json()["data"]
    assert pdf_body["pdf_url"]
    assert pdf_body["pdf_url_expires_at"]
    assert fake_minio.head_object(f"coach-recap/{recap_id}.pdf")

    listing = await client.get(
        "/v1/coach/sessions/recaps",
        headers=coach_headers,
    )
    assert listing.status_code == 200, listing.text
    items = listing.json()["data"]["items"]
    assert items[0]["id"] == recap_id
    assert items[0]["pdf_url"]
