"""M8-05 · 教练作业派发 service."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.coach import CoachAssignedTask, CoachProfile
from app.models.training import Drill, TrainingPlan, TrainingTask
from app.models.user import User
from app.schemas.coach_task import (
    CoachAssignedTaskListResponse,
    CoachAssignedTaskRead,
    CoachTaskAssignRequest,
    CoachTaskDrillBrief,
    CoachTaskStudentBrief,
)
from app.services.coach_student_service import require_active_relation
from app.services.training_service import _china_today, week_bounds

logger = get_logger("coach_task")


def ensure_coach_tasks_enabled() -> None:
    if not settings.PHASE2_COACH_TASKS_ENABLED:
        raise NotFoundError(code=40406, message="教练作业派发未开放")


def _normalize_target_week(d: date) -> date:
    monday, _ = week_bounds(d)
    return monday


async def _assert_daily_limit(db: AsyncSession, *, coach_user_id: str) -> None:
    today = _china_today()
    start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    count = (
        await db.execute(
            select(func.count())
            .select_from(CoachAssignedTask)
            .where(
                CoachAssignedTask.coach_user_id == coach_user_id,
                CoachAssignedTask.created_at >= start,
            )
        )
    ).scalar_one()
    if count >= settings.COACH_TASK_MAX_PER_DAY:
        raise BadRequestError(code=40001, message="今日派发任务已达上限")


async def _get_drill(db: AsyncSession, drill_id: str) -> Drill:
    drill = await db.get(Drill, drill_id)
    if drill is None or not drill.is_active:
        raise NotFoundError(code=40406, message="训练动作不存在或已下架")
    return drill


async def ensure_week_plan(db: AsyncSession, *, user_id: str, week_monday: date) -> TrainingPlan:
    monday = _normalize_target_week(week_monday)
    sunday = monday + timedelta(days=6)
    stmt = (
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.tasks))
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.week_start == monday,
        )
    )
    plan = (await db.execute(stmt)).scalar_one_or_none()
    if plan is not None:
        return plan

    plan = TrainingPlan(
        id=new_id("plan"),
        user_id=user_id,
        week_start=monday,
        week_end=sunday,
        source_analysis_id=None,
        total_tasks=0,
        completed_tasks=0,
    )
    db.add(plan)
    await db.flush()
    return plan


def _scheduled_date_for_week(target_week: date) -> date:
    today = _china_today()
    week_end = target_week + timedelta(days=6)
    if today < target_week:
        return target_week
    if today > week_end:
        return week_end
    return today


async def _serialize_task(
    db: AsyncSession, row: CoachAssignedTask, *, include_student: bool
) -> CoachAssignedTaskRead:
    student_brief: CoachTaskStudentBrief | None = None
    if include_student:
        student = await db.get(User, row.student_user_id)
        student_brief = CoachTaskStudentBrief(
            id=row.student_user_id,
            nickname=student.nickname if student else None,
        )
    drill_brief: CoachTaskDrillBrief | None = None
    if row.drill_id:
        drill = await db.get(Drill, row.drill_id)
        if drill:
            drill_brief = CoachTaskDrillBrief(id=drill.id, name=drill.name)
    return CoachAssignedTaskRead(
        id=row.id,
        coach_user_id=row.coach_user_id,
        student_user_id=row.student_user_id,
        relation_id=row.relation_id,
        source_type=row.source_type,  # type: ignore[arg-type]
        drill_id=row.drill_id,
        target_week=row.target_week,
        target_count=row.target_count,
        target_issue=row.target_issue,
        coach_note=row.coach_note,
        training_task_id=row.training_task_id,
        status=row.status,  # type: ignore[arg-type]
        completed_at=row.completed_at,
        created_at=row.created_at,
        student=student_brief,
        drill=drill_brief,
    )


async def assign_task(
    db: AsyncSession,
    *,
    coach: User,
    payload: CoachTaskAssignRequest,
) -> CoachAssignedTaskRead:
    ensure_coach_tasks_enabled()
    await _assert_daily_limit(db, coach_user_id=coach.id)
    relation = await require_active_relation(
        db, coach=coach, student_id=payload.student_user_id
    )
    if payload.source_type != "drill":
        raise BadRequestError(code=40001, message="当前仅支持 drill 作业派发")
    if not payload.drill_id:
        raise BadRequestError(code=40001, message="drill 作业须提供 drill_id")

    drill = await _get_drill(db, payload.drill_id)
    target_week = _normalize_target_week(payload.target_week)
    coach_note = (payload.coach_note or "").strip() or None

    plan = await ensure_week_plan(
        db, user_id=payload.student_user_id, week_monday=target_week
    )
    scheduled = _scheduled_date_for_week(target_week)
    sort_order = len(plan.tasks or [])
    task = TrainingTask(
        id=new_id("task"),
        plan_id=plan.id,
        user_id=payload.student_user_id,
        drill_id=drill.id,
        scheduled_date=scheduled,
        sort_order=sort_order,
        status="pending",
    )
    db.add(task)
    plan.total_tasks = (plan.total_tasks or 0) + 1

    assigned = CoachAssignedTask(
        id=new_id("ctask"),
        coach_user_id=coach.id,
        student_user_id=payload.student_user_id,
        relation_id=relation.id,
        source_type="drill",
        drill_id=drill.id,
        target_week=target_week,
        target_count=payload.target_count,
        target_issue=(payload.target_issue or "").strip() or None,
        coach_note=coach_note,
        training_task_id=task.id,
        status="assigned",
    )
    db.add(assigned)
    await db.flush()

    if coach_note:
        from app.services.content_moderation_service import moderate_coach_task_note

        await moderate_coach_task_note(
            db, assigned_id=assigned.id, coach_note=coach_note
        )

    logger.info(
        "coach_task_assigned",
        assigned_id=assigned.id,
        coach_id=coach.id,
        student_id=payload.student_user_id,
        drill_id=drill.id,
        task_id=task.id,
    )
    from app.services.coach_dashboard_service import invalidate_dashboard_for_coach

    await invalidate_dashboard_for_coach(
        coach_user_id=coach.id, student_user_id=payload.student_user_id
    )
    return await _serialize_task(db, assigned, include_student=True)


async def list_coach_tasks(
    db: AsyncSession,
    *,
    coach: User,
    student_user_id: str | None = None,
    status: str | None = None,
) -> CoachAssignedTaskListResponse:
    ensure_coach_tasks_enabled()
    valid_statuses = {"assigned", "started", "done", "expired"}
    if status and status not in valid_statuses:
        raise BadRequestError(code=40002, message="不支持的 status 筛选")

    stmt = select(CoachAssignedTask).where(CoachAssignedTask.coach_user_id == coach.id)
    if student_user_id:
        stmt = stmt.where(CoachAssignedTask.student_user_id == student_user_id)
    if status:
        stmt = stmt.where(CoachAssignedTask.status == status)
    stmt = stmt.order_by(CoachAssignedTask.created_at.desc())
    rows = list((await db.execute(stmt)).scalars().all())
    items = [await _serialize_task(db, row, include_student=True) for row in rows]
    return CoachAssignedTaskListResponse(items=items, total=len(items))


async def sync_on_training_task_complete(
    db: AsyncSession, *, task_id: str
) -> CoachAssignedTask | None:
    row = await db.execute(
        select(CoachAssignedTask).where(CoachAssignedTask.training_task_id == task_id)
    )
    assigned = row.scalar_one_or_none()
    if assigned is None or assigned.status == "done":
        return assigned
    assigned.status = "done"
    assigned.completed_at = datetime.now(UTC)
    await db.flush()
    logger.info(
        "coach_task_completed",
        assigned_id=assigned.id,
        task_id=task_id,
    )
    return assigned


async def load_coach_refs_for_tasks(
    db: AsyncSession, *, task_ids: list[str]
) -> dict[str, tuple[str, str, int, str | None]]:
    """task_id → (coach_user_id, coach_display_name, target_count, coach_note)."""

    if not task_ids:
        return {}
    rows = await db.execute(
        select(CoachAssignedTask, CoachProfile.display_name)
        .outerjoin(CoachProfile, CoachProfile.user_id == CoachAssignedTask.coach_user_id)
        .where(
            CoachAssignedTask.training_task_id.in_(task_ids),
            CoachAssignedTask.status != "expired",
        )
    )
    out: dict[str, tuple[str, str, int, str | None]] = {}
    from app.services.content_moderation_service import is_coach_note_visible_to_student

    for assigned, display_name in rows.all():
        if not assigned.training_task_id:
            continue
        note = assigned.coach_note
        if note and not await is_coach_note_visible_to_student(
            db, assigned_id=assigned.id, coach_note=note
        ):
            note = None
        out[assigned.training_task_id] = (
            assigned.coach_user_id,
            display_name or "教练",
            assigned.target_count,
            note,
        )
    return out


__all__ = [
    "assign_task",
    "ensure_coach_tasks_enabled",
    "list_coach_tasks",
    "load_coach_refs_for_tasks",
    "sync_on_training_task_complete",
]
