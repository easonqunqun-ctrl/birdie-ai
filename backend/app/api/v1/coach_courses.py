"""P2-M11-06 · 教练定制课程写端点（白名单守门，M8 认证就位前）."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.courses import _ensure_courses_enabled
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.course import (
    CoachCourseCreate,
    CoachCourseUpdate,
    CoachLessonCreate,
    CourseRead,
    LessonRead,
)
from app.services import coach_course_service as coach_svc

router = APIRouter()


@router.get(
    "",
    summary="列出我创建的教练定制课程（M11-06）",
    response_model=APIResponse[list[CourseRead]],
)
async def list_my_coach_courses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_courses_enabled()
    coach_svc.assert_coach_course_author(user)
    courses = await coach_svc.list_coach_courses(db, user.id)
    return ok([CourseRead.model_validate(c) for c in courses])


@router.post(
    "",
    summary="创建教练定制课程草稿（M11-06）",
    response_model=APIResponse[CourseRead],
)
async def create_coach_course(
    payload: CoachCourseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_courses_enabled()
    course = await coach_svc.create_coach_course(db, user=user, payload=payload)
    await db.commit()
    return ok(CourseRead.model_validate(course))


@router.patch(
    "/{course_id}",
    summary="更新教练定制课程草稿（M11-06）",
    response_model=APIResponse[CourseRead],
)
async def update_coach_course(
    course_id: str,
    payload: CoachCourseUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_courses_enabled()
    coach_svc.assert_coach_course_author(user)
    course = await coach_svc.update_coach_course(
        db, user_id=user.id, course_id=course_id, payload=payload
    )
    await db.commit()
    return ok(CourseRead.model_validate(course))


@router.post(
    "/{course_id}/lessons",
    summary="为教练课程添加课时（M11-06）",
    response_model=APIResponse[LessonRead],
)
async def add_coach_course_lesson(
    course_id: str,
    payload: CoachLessonCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_courses_enabled()
    coach_svc.assert_coach_course_author(user)
    lesson = await coach_svc.add_coach_lesson(
        db, user_id=user.id, course_id=course_id, payload=payload
    )
    await db.commit()
    return ok(LessonRead.model_validate(lesson))


@router.post(
    "/{course_id}/publish",
    summary="发布教练定制课程（M11-06）",
    response_model=APIResponse[CourseRead],
)
async def publish_coach_course(
    course_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_courses_enabled()
    coach_svc.assert_coach_course_author(user)
    course = await coach_svc.publish_coach_course(
        db, user_id=user.id, course_id=course_id
    )
    await db.commit()
    return ok(CourseRead.model_validate(course))


@router.post(
    "/{course_id}/unpublish",
    summary="下架教练定制课程以便再编辑（M11-06）",
    response_model=APIResponse[CourseRead],
)
async def unpublish_coach_course(
    course_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_courses_enabled()
    coach_svc.assert_coach_course_author(user)
    course = await coach_svc.unpublish_coach_course(
        db, user_id=user.id, course_id=course_id
    )
    await db.commit()
    return ok(CourseRead.model_validate(course))
