"""二期 M11 课程体系（学习路径）读端点（对齐 docs/23 §7.1 · M11-02）.

只暴露**已发布**的课程 / 课时给小程序：
- ``GET /v1/courses?stage=N`` — 列出已发布课程
- ``GET /v1/courses/{course_id}`` — 单课程详情
- ``GET /v1/courses/{course_id}/lessons`` — 该课程下的全部课时（按 sort_order）

灰度
----
统一守门：``PHASE2_COURSES_ENABLED=False`` 时所有端点返回 ``404``，与 M9 系列
``_ensure_profile_v2_enabled`` 同套模式（kickoff §4.2）。

写入 / 进度 / 证书
----------------
本 PR 不暴露写端点。``create_course`` / ``create_lesson`` / ``upsert_progress``
等仍只在 ``course_service`` 里；后续 M11-03（UI 触发 in_progress / passed）
和 M11-05（证书）会按需新增对应路由。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas.base import APIResponse, ok
from app.schemas.course import (
    CourseLessonsResponse,
    CourseRead,
    LessonRead,
)
from app.services import course_service

router = APIRouter()


def _ensure_courses_enabled() -> None:
    """守门：未启用 PHASE2_COURSES_ENABLED 直接 404，与 M11-03 UI 守门一致."""

    if not settings.PHASE2_COURSES_ENABLED:
        raise NotFoundError(code=40406, message="课程功能未开放")


@router.get(
    "",
    summary="列出已发布课程（M11-02）",
    response_model=APIResponse[list[CourseRead]],
)
async def list_courses(
    stage: int | None = Query(None, ge=1, le=7, description="按阶段筛选（可选）"),
    db: AsyncSession = Depends(get_db),
):
    """返回所有已发布课程，按 ``stage`` / ``sort_order`` 升序.

    设计：不做分页（7 阶 × 单阶 5-10 课，总量上限可控）；后续若超 50 门再加分页。
    """

    _ensure_courses_enabled()
    courses = await course_service.list_published_courses(db, stage=stage)
    return ok([CourseRead.model_validate(c) for c in courses])


@router.get(
    "/{course_id}",
    summary="获取单课程详情（M11-02）",
    response_model=APIResponse[CourseRead],
)
async def get_course_detail(
    course_id: str,
    db: AsyncSession = Depends(get_db),
):
    """单课程详情；未发布课程一律 404（不暴露草稿元数据）."""

    _ensure_courses_enabled()
    course = await course_service.get_course(db, course_id)
    if course is None or not course.is_published:
        raise NotFoundError(code=40406, message="课程不存在或未发布")
    return ok(CourseRead.model_validate(course))


@router.get(
    "/{course_id}/lessons",
    summary="列出课程下的全部课时（M11-02）",
    response_model=APIResponse[CourseLessonsResponse],
)
async def list_course_lessons(
    course_id: str,
    db: AsyncSession = Depends(get_db),
):
    """按 sort_order 升序返回该课程下所有 lesson.

    课程未发布 → 404（service 层已在 ``published_only=True`` 下返回空列表，
    这里二次校验避免空列表被误解为"该课程合法但没有 lesson"）。
    """

    _ensure_courses_enabled()
    course = await course_service.get_course(db, course_id)
    if course is None or not course.is_published:
        raise NotFoundError(code=40406, message="课程不存在或未发布")

    lessons = await course_service.list_lessons_by_course(db, course_id)
    items = [LessonRead.model_validate(lsn) for lsn in lessons]
    return ok(
        CourseLessonsResponse(
            course_id=course_id, items=items, total=len(items)
        )
    )
