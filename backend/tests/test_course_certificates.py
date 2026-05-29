"""M11-05 · 证书 service + API 测试."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.course import COURSE_STATUS_PASSED
from app.models.user import User
from app.schemas.course import CourseCreate, LessonCreate, UserCourseProgressUpdate
from app.services import course_service as svc
from app.services.course_certificate_service import badge_label_for_stage


@pytest.fixture
def courses_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COURSES_ENABLED", True)


async def _make_user(db) -> User:
    u = User(
        id=new_id("usr"),
        wechat_openid=f"oid_{new_id('x')[-8:]}",
        nickname="测试球友",
    )
    db.add(u)
    await db.flush()
    return u


async def _make_drill(db, n: int):
    from app.models.training import Drill

    d = Drill(
        id=new_id("drl"),
        code=f"drill_{n}_{new_id('x')[-6:]}",
        title=f"Drill {n}",
        category="full_swing",
        difficulty="beginner",
        duration_minutes=10,
        sort_order=n,
    )
    db.add(d)
    await db.flush()
    return d


@pytest.mark.asyncio
async def test_maybe_issue_certificate_populates_metadata() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        drill = await _make_drill(db, 1)
        course = await svc.create_course(
            db,
            CourseCreate(code=f"c_{new_id('x')[-6:]}", title="基础挥杆通关", stage=1),
        )
        lesson = await svc.create_lesson(
            db,
            LessonCreate(
                course_id=course.id,
                code=f"l_{new_id('x')[-6:]}",
                title="L",
                sort_order=0,
                drill_ids=[drill.id],
            ),
        )
        await svc.upsert_progress(
            db,
            user_id=u.id,
            lesson_id=lesson.id,
            payload=UserCourseProgressUpdate(status=COURSE_STATUS_PASSED),
        )
        cert = await svc.maybe_issue_certificate(db, user_id=u.id, course_id=course.id)
        assert cert is not None
        assert cert.extra_metadata["course_title"] == "基础挥杆通关"
        assert cert.extra_metadata["badge_label"] == badge_label_for_stage(1)
        assert cert.extra_metadata["holder_name"] == "测试球友"
        assert cert.cert_url == f"certs/{u.id}/{cert.id}.png"


@pytest.mark.asyncio
async def test_list_certificates_api(
    client: AsyncClient, courses_enabled: None
) -> None:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"cert_{new_id('x')[-10:]}"},
    )
    assert login.status_code == 200
    user_id = login.json()["data"]["user"]["id"]
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}

    async with AsyncSessionLocal() as db:
        user_row = await db.get(User, user_id)
        assert user_row is not None
        user_row.nickname = "证书测试"
        drill = await _make_drill(db, 2)
        course = await svc.create_course(
            db,
            CourseCreate(code=f"c_{new_id('x')[-6:]}", title="Stage2", stage=2),
        )
        lesson = await svc.create_lesson(
            db,
            LessonCreate(
                course_id=course.id,
                code=f"l_{new_id('x')[-6:]}",
                title="L",
                sort_order=0,
                drill_ids=[drill.id],
            ),
        )
        await svc.upsert_progress(
            db,
            user_id=user_id,
            lesson_id=lesson.id,
            payload=UserCourseProgressUpdate(status=COURSE_STATUS_PASSED),
        )
        cert = await svc.maybe_issue_certificate(
            db, user_id=user_id, course_id=course.id
        )
        await db.commit()
        cert_id = cert.id

    r_list = await client.get("/v1/users/me/certificates", headers=headers)
    assert r_list.status_code == 200
    data = r_list.json()["data"]
    assert len(data) == 1
    assert data[0]["stage"] == 2
    assert data[0]["badge_label"] == badge_label_for_stage(2)

    r_stage = await client.get("/v1/users/me/course-stage", headers=headers)
    assert r_stage.status_code == 200
    stage_payload = r_stage.json()["data"]
    assert stage_payload["current_stage"] == 3
    assert stage_payload["earned_stages"] == [2]

    r_one = await client.get(f"/v1/users/me/certificates/{cert_id}", headers=headers)
    assert r_one.status_code == 200
    assert r_one.json()["data"]["course_title"] == "Stage2"


@pytest.mark.asyncio
async def test_certificates_404_when_flag_off(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "PHASE2_COURSES_ENABLED", False)
    resp = await client.get("/v1/users/me/certificates")
    assert resp.status_code == 404
