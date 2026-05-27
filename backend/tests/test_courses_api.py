"""M11-02 GET /v1/courses 读端点 + flag 守门测试.

覆盖
----
1. PHASE2_COURSES_ENABLED=False → 三个端点全部 404（不暴露存在性）
2. PHASE2_COURSES_ENABLED=True + 无内容 → list 返空，detail 404
3. PHASE2_COURSES_ENABLED=True + seed 后 → 课程 + lessons 正常拿到
4. 草稿课程（is_published=False）→ list 不出现 + detail / lessons 都 404
5. stage 过滤参数生效
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.schemas.course import CourseCreate, LessonCreate
from app.services import course_service as svc


@pytest.fixture
def courses_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """灰度开关临时打开；不要修改全局 settings 文件。"""

    monkeypatch.setattr(settings, "PHASE2_COURSES_ENABLED", True)


@pytest.fixture
def courses_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COURSES_ENABLED", False)


@pytest.mark.asyncio
async def test_list_courses_404_when_flag_off(
    client: AsyncClient, courses_disabled: None
) -> None:
    resp = await client.get("/v1/courses")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_course_detail_404_when_flag_off(
    client: AsyncClient, courses_disabled: None
) -> None:
    resp = await client.get("/v1/courses/crs_anything")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_course_lessons_404_when_flag_off(
    client: AsyncClient, courses_disabled: None
) -> None:
    resp = await client.get("/v1/courses/crs_anything/lessons")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_courses_returns_seeded_course(
    client: AsyncClient, courses_enabled: None
) -> None:
    """seed → list 应包含本课程 + stage=1."""

    async with AsyncSessionLocal() as db:
        await svc.seed_initial_courses(db)
        await db.commit()

    resp = await client.get("/v1/courses")
    assert resp.status_code == 200
    payload = resp.json()["data"]
    codes = {c["code"] for c in payload}
    assert "stage1-basic-swing-v1" in codes
    # 全部 is_published=True
    assert all(c["is_published"] for c in payload)


@pytest.mark.asyncio
async def test_list_courses_filters_by_stage(
    client: AsyncClient, courses_enabled: None
) -> None:
    """stage=1 只返 stage=1；stage=7 应返空（seed 只插了 stage 1）."""

    async with AsyncSessionLocal() as db:
        await svc.seed_initial_courses(db)
        await db.commit()

    r1 = await client.get("/v1/courses?stage=1")
    r7 = await client.get("/v1/courses?stage=7")
    assert r1.status_code == 200 and r7.status_code == 200
    assert all(c["stage"] == 1 for c in r1.json()["data"])
    assert r7.json()["data"] == []


@pytest.mark.asyncio
async def test_get_course_lessons_returns_sorted(
    client: AsyncClient, courses_enabled: None
) -> None:
    async with AsyncSessionLocal() as db:
        [course] = await svc.seed_initial_courses(db)
        await db.commit()
        course_id = course.id

    resp = await client.get(f"/v1/courses/{course_id}/lessons")
    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["course_id"] == course_id
    assert payload["total"] == 3
    sort_orders = [l["sort_order"] for l in payload["items"]]
    assert sort_orders == [1, 2, 3]
    # transcript 字段必须暴露（M11-03 渲染依赖）
    assert all(l["transcript"] for l in payload["items"])


@pytest.mark.asyncio
async def test_unpublished_course_invisible_to_public_endpoints(
    client: AsyncClient, courses_enabled: None
) -> None:
    """草稿课程 list 不出现；detail / lessons 都 404."""

    from app.core.security import new_id

    async with AsyncSessionLocal() as db:
        draft = await svc.create_course(
            db,
            CourseCreate(
                code=f"draft_{new_id('x')[-6:]}",
                title="Draft",
                stage=3,
            ),
        )
        draft_id = draft.id
        await db.commit()

    r_list = await client.get("/v1/courses?stage=3")
    assert r_list.status_code == 200
    assert all(c["id"] != draft_id for c in r_list.json()["data"])

    r_detail = await client.get(f"/v1/courses/{draft_id}")
    r_lessons = await client.get(f"/v1/courses/{draft_id}/lessons")
    assert r_detail.status_code == 404
    assert r_lessons.status_code == 404


@pytest.mark.asyncio
async def test_get_lessons_404_for_nonexistent_course(
    client: AsyncClient, courses_enabled: None
) -> None:
    resp = await client.get("/v1/courses/crs_nope_does_not_exist/lessons")
    assert resp.status_code == 404
