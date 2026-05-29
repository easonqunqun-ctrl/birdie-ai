"""M8-03 最小子集 · 教练-学员师生关系（M13-10 旁观守门）."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.coach import CoachStudentRelation
from app.models.user import User
from app.services.coach_course_service import assert_coach_course_author, coach_course_user_ids

logger = get_logger("coach_student")


async def require_active_relation(
    db: AsyncSession, *, coach: User, student_id: str
) -> CoachStudentRelation:
    """校验 active 师生关系；不存在则 404."""

    if coach.id in coach_course_user_ids():
        pass
    elif settings.PHASE2_COACH_ENABLED:
        from app.services.coach_profile_service import assert_active_coach

        await assert_active_coach(db, user=coach)
    else:
        assert_coach_course_author(coach)
    row = await db.execute(
        select(CoachStudentRelation).where(
            CoachStudentRelation.coach_user_id == coach.id,
            CoachStudentRelation.student_user_id == student_id,
            CoachStudentRelation.status == "active",
        )
    )
    relation = row.scalar_one_or_none()
    if relation is None:
        raise NotFoundError(code=40406, message="学员不存在或无师生关系")
    return relation


async def ensure_relation(
    db: AsyncSession,
    *,
    coach_user_id: str,
    student_user_id: str,
    status: str = "active",
) -> CoachStudentRelation:
    """测试 / 种子数据：幂等创建师生关系."""

    row = await db.execute(
        select(CoachStudentRelation).where(
            CoachStudentRelation.coach_user_id == coach_user_id,
            CoachStudentRelation.student_user_id == student_user_id,
        )
    )
    existing = row.scalar_one_or_none()
    if existing is not None:
        if existing.status != status:
            existing.status = status
            await db.flush()
        return existing

    relation = CoachStudentRelation(
        id=new_id("csr"),
        coach_user_id=coach_user_id,
        student_user_id=student_user_id,
        status=status,
    )
    db.add(relation)
    await db.flush()
    logger.info(
        "coach_student_relation_created",
        coach_user_id=coach_user_id,
        student_user_id=student_user_id,
    )
    return relation


__all__ = ["ensure_relation", "require_active_relation"]
