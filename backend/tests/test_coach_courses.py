"""M11-06 · 教练定制课程 API + service 测试."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.training import Drill
from app.models.user import User
from app.schemas.course import CoachCourseCreate
from app.services import coach_course_service as coach_svc


@pytest.fixture
def courses_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COURSES_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", True)


async def _make_user(db) -> User:
    u = User(
        id=new_id("usr"),
        wechat_openid=f"oid_{new_id('x')[-8:]}",
        nickname="教练测试",
        invite_code=new_id("inv")[-6:].upper(),
    )
    db.add(u)
    await db.flush()
    return u


async def _make_drill(db) -> Drill:
    d = Drill(
        id=new_id("drl"),
        name=f"drill_{new_id('x')[-6:]}",
        description="coach course test",
        duration_minutes=10,
        difficulty="easy",
    )
    db.add(d)
    await db.flush()
    return d


@pytest.mark.asyncio
async def test_create_coach_course_sets_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    async with AsyncSessionLocal() as db:
        user = await _make_user(db)
        monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", user.id)
        course = await coach_svc.create_coach_course(
            db,
            user=user,
            payload=CoachCourseCreate(title="定制课", stage=2),
        )
        assert course.created_by_user_id == user.id
        assert course.code.startswith("coach-")
        assert course.is_published is False


@pytest.mark.asyncio
async def test_non_allowlisted_user_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    async with AsyncSessionLocal() as db:
        user = await _make_user(db)
        monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", "usr_other")
        from app.core.exceptions import ForbiddenError

        with pytest.raises(ForbiddenError):
            await coach_svc.create_coach_course(
                db,
                user=user,
                payload=CoachCourseCreate(title="x", stage=1),
            )


@pytest.mark.asyncio
async def test_coach_course_publish_flow_api(
    client: AsyncClient, courses_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"coach_{new_id('x')[-10:]}"},
    )
    user_id = login.json()["data"]["user"]["id"]
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", user_id)

    switch = await client.post(
        "/v1/auth/role-switch",
        json={"role": "coach"},
        headers=headers,
    )
    assert switch.status_code == 200, switch.text
    headers = {"Authorization": f"Bearer {switch.json()['data']['token']}"}

    async with AsyncSessionLocal() as db:
        drill = await _make_drill(db)
        await db.commit()
        drill_id = drill.id

    r_create = await client.post(
        "/v1/users/me/coach/courses",
        headers=headers,
        json={"title": "教练专属课", "stage": 3, "description": "定制"},
    )
    assert r_create.status_code == 200
    course_id = r_create.json()["data"]["id"]

    r_lesson = await client.post(
        f"/v1/users/me/coach/courses/{course_id}/lessons",
        headers=headers,
        json={
            "code": f"lsn_{new_id('x')[-6:]}",
            "title": "第一课",
            "sort_order": 1,
            "drill_ids": [drill_id],
        },
    )
    assert r_lesson.status_code == 200

    r_pub = await client.post(
        f"/v1/users/me/coach/courses/{course_id}/publish",
        headers=headers,
    )
    assert r_pub.status_code == 200
    assert r_pub.json()["data"]["is_published"] is True

    r_list_public = await client.get("/v1/courses?stage=3")
    assert any(c["id"] == course_id for c in r_list_public.json()["data"])

    r_list_mine = await client.get("/v1/users/me/coach/courses", headers=headers)
    assert len(r_list_mine.json()["data"]) == 1


@pytest.mark.asyncio
async def test_coach_courses_403_when_not_allowlisted(
    client: AsyncClient, courses_enabled: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", "")
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"noc_{new_id('x')[-10:]}"},
    )
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    resp = await client.get("/v1/users/me/coach/courses", headers=headers)
    assert resp.status_code == 403
