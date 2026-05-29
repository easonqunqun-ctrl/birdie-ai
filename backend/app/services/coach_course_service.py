"""P2-M11-06 · 教练定制课程（写端点 + 所有权校验）.

M8 教练认证未就位前，用 ``settings.COACH_COURSE_USER_IDS`` 白名单守门；
认证就位后仍保留白名单作 seed 教练兜底（见 wait-for-triggers §2.16）。
"""

from __future__ import annotations

from nanoid import generate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.course import Course, Lesson
from app.models.user import User
from app.schemas.course import CoachCourseCreate, CoachCourseUpdate, CoachLessonCreate, CourseCreate, LessonCreate
from app.services import course_service

logger = get_logger("coach_course")

_ID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def coach_course_user_ids() -> frozenset[str]:
    raw = (settings.COACH_COURSE_USER_IDS or "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def assert_coach_course_author(user: User) -> None:
    """同步守门：仅 seed 白名单（M8-01 就位后写端点改 ``assert_coach_author``）."""

    if user.id in coach_course_user_ids():
        return
    raise ForbiddenError(code=40301, message="无权创建教练定制课程")


async def assert_coach_author(db: AsyncSession, user: User) -> None:
    """M8-01：seed 白名单或 ``coach_profiles.status=active``."""

    if user.id in coach_course_user_ids():
        return
    if settings.PHASE2_COACH_ENABLED:
        from app.services.coach_profile_service import assert_active_coach

        await assert_active_coach(db, user=user)
        return
    raise ForbiddenError(code=40301, message="无权操作教练端点")


async def _get_owned_course(
    db: AsyncSession, *, user_id: str, course_id: str
) -> Course:
    course = await course_service.get_course(db, course_id)
    if course is None or course.created_by_user_id != user_id:
        raise NotFoundError(code=40406, message="课程不存在")
    return course


def _unique_course_code(user_id: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    suffix = generate(alphabet=_ID_ALPHABET, size=6)
    user_part = user_id.rsplit("_", 1)[-1][:8]
    return f"coach-{user_part}-{suffix}"


async def list_coach_courses(db: AsyncSession, user_id: str) -> list[Course]:
    rows = await db.execute(
        select(Course)
        .where(Course.created_by_user_id == user_id)
        .order_by(Course.created_at.desc())
    )
    return list(rows.scalars().all())


async def create_coach_course(
    db: AsyncSession, *, user: User, payload: CoachCourseCreate
) -> Course:
    await assert_coach_author(db, user)
    code = _unique_course_code(user.id, payload.code)
    course = await course_service.create_course(
        db,
        CourseCreate(
            code=code,
            title=payload.title,
            subtitle=payload.subtitle,
            cover_url=payload.cover_url,
            stage=payload.stage,
            sort_order=payload.sort_order,
            is_member_only=payload.is_member_only,
            description=payload.description,
            learning_objectives=list(payload.learning_objectives),
            estimated_minutes=payload.estimated_minutes,
            created_by_user_id=user.id,
        ),
    )
    logger.info("coach_course_created", course_id=course.id, user_id=user.id)
    return course


async def update_coach_course(
    db: AsyncSession,
    *,
    user_id: str,
    course_id: str,
    payload: CoachCourseUpdate,
) -> Course:
    course = await _get_owned_course(db, user_id=user_id, course_id=course_id)
    if course.is_published:
        raise BadRequestError(code=40903, message="已发布课程请先下架再编辑")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "learning_objectives" and value is not None:
            setattr(course, key, list(value))
        elif value is not None:
            setattr(course, key, value)
    await db.flush()
    return course


async def add_coach_lesson(
    db: AsyncSession,
    *,
    user_id: str,
    course_id: str,
    payload: CoachLessonCreate,
) -> Lesson:
    await _get_owned_course(db, user_id=user_id, course_id=course_id)
    return await course_service.create_lesson(
        db,
        LessonCreate(
            course_id=course_id,
            code=payload.code,
            title=payload.title,
            sort_order=payload.sort_order,
            duration_minutes=payload.duration_minutes,
            video_url=payload.video_url,
            transcript=payload.transcript,
            drill_ids=list(payload.drill_ids),
            pro_clip_ids=list(payload.pro_clip_ids),
            quiz_payload=payload.quiz_payload,
            pass_criteria=dict(payload.pass_criteria),
        ),
    )


async def publish_coach_course(
    db: AsyncSession, *, user_id: str, course_id: str
) -> Course:
    await _get_owned_course(db, user_id=user_id, course_id=course_id)
    return await course_service.publish_course(db, course_id)


async def unpublish_coach_course(
    db: AsyncSession, *, user_id: str, course_id: str
) -> Course:
    course = await _get_owned_course(db, user_id=user_id, course_id=course_id)
    if not course.is_published:
        return course
    course.is_published = False
    course.published_at = None
    await db.flush()
    logger.info("coach_course_unpublished", course_id=course.id, user_id=user_id)
    return course


__all__ = [
    "add_coach_lesson",
    "assert_coach_author",
    "assert_coach_course_author",
    "coach_course_user_ids",
    "create_coach_course",
    "list_coach_courses",
    "publish_coach_course",
    "unpublish_coach_course",
    "update_coach_course",
]
