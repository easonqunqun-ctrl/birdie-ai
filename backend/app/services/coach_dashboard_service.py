"""M8-06 · 教练学员看板聚合 service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import CoachStudentRelationError, NotFoundError
from app.core.logging import get_logger
from app.models.analysis import SwingAnalysis
from app.models.coach import AnalysisAnnotation, CoachAssignedTask, CoachStudentRelation
from app.models.training import Drill
from app.models.user import User
from app.schemas.coach_dashboard import (
    CoachDashboardAnalysisBrief,
    CoachDashboardAnnotationBrief,
    CoachDashboardDetailResponse,
    CoachDashboardListResponse,
    CoachDashboardStudentItem,
    CoachDashboardTaskBrief,
)
from app.services import coach_dashboard_cache as dash_cache
from app.services.coach_student_service import require_active_relation

logger = get_logger("coach_dashboard")

MAX_STUDENTS = 100
RECENT_ANALYSES_LIMIT = 5
RECENT_ANNOTATIONS_LIMIT = 5


def ensure_coach_dashboard_enabled() -> None:
    if not settings.PHASE2_COACH_DASHBOARD_ENABLED:
        raise NotFoundError(code=40406, message="教练学员看板未开放")


def _now() -> datetime:
    return datetime.now(UTC)


def _needs_response(
    *,
    has_analysis_24h: bool,
    last_annotation_at: datetime | None,
    now: datetime,
) -> bool:
    if not has_analysis_24h:
        return False
    cutoff = now - timedelta(hours=24)
    if last_annotation_at is None:
        return True
    ann_at = last_annotation_at
    if ann_at.tzinfo is None:
        ann_at = ann_at.replace(tzinfo=UTC)
    return ann_at < cutoff


async def _load_active_relations(
    db: AsyncSession, *, coach_user_id: str
) -> list[tuple[CoachStudentRelation, User]]:
    rows = await db.execute(
        select(CoachStudentRelation, User)
        .join(User, User.id == CoachStudentRelation.student_user_id)
        .where(
            CoachStudentRelation.coach_user_id == coach_user_id,
            CoachStudentRelation.status == "active",
        )
        .order_by(CoachStudentRelation.accepted_at.desc().nullslast())
        .limit(MAX_STUDENTS)
    )
    return list(rows.all())


async def _aggregate_for_students(
    db: AsyncSession,
    *,
    coach_user_id: str,
    student_ids: list[str],
    now: datetime,
) -> dict[str, dict]:
    if not student_ids:
        return {}

    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(days=1)

    analyses_7d_rows = await db.execute(
        select(SwingAnalysis.user_id, func.count())
        .where(
            SwingAnalysis.user_id.in_(student_ids),
            SwingAnalysis.deleted_at.is_(None),
            SwingAnalysis.created_at >= week_ago,
        )
        .group_by(SwingAnalysis.user_id)
    )
    analyses_7d_map = dict(analyses_7d_rows.all())

    last_analysis_rows = await db.execute(
        select(SwingAnalysis.user_id, func.max(SwingAnalysis.created_at))
        .where(
            SwingAnalysis.user_id.in_(student_ids),
            SwingAnalysis.deleted_at.is_(None),
        )
        .group_by(SwingAnalysis.user_id)
    )
    last_analysis_map = dict(last_analysis_rows.all())

    analysis_24h_rows = await db.execute(
        select(SwingAnalysis.user_id, func.count())
        .where(
            SwingAnalysis.user_id.in_(student_ids),
            SwingAnalysis.deleted_at.is_(None),
            SwingAnalysis.created_at >= day_ago,
        )
        .group_by(SwingAnalysis.user_id)
    )
    analysis_24h_map = dict(analysis_24h_rows.all())

    last_ann_rows = await db.execute(
        select(
            AnalysisAnnotation.student_user_id,
            func.max(AnalysisAnnotation.created_at),
        )
        .where(
            AnalysisAnnotation.coach_user_id == coach_user_id,
            AnalysisAnnotation.student_user_id.in_(student_ids),
        )
        .group_by(AnalysisAnnotation.student_user_id)
    )
    last_ann_map = dict(last_ann_rows.all())

    pending_task_rows = await db.execute(
        select(CoachAssignedTask.student_user_id, func.count())
        .where(
            CoachAssignedTask.coach_user_id == coach_user_id,
            CoachAssignedTask.student_user_id.in_(student_ids),
            CoachAssignedTask.status.in_(("assigned", "started")),
        )
        .group_by(CoachAssignedTask.student_user_id)
    )
    pending_task_map = dict(pending_task_rows.all())

    out: dict[str, dict] = {}
    for sid in student_ids:
        last_ann = last_ann_map.get(sid)
        out[sid] = {
            "analyses_7d": int(analyses_7d_map.get(sid, 0)),
            "last_analysis_at": last_analysis_map.get(sid),
            "last_annotation_at": last_ann,
            "pending_tasks": int(pending_task_map.get(sid, 0)),
            "needs_response": _needs_response(
                has_analysis_24h=int(analysis_24h_map.get(sid, 0)) > 0,
                last_annotation_at=last_ann,
                now=now,
            ),
        }
    return out


def _sort_students(items: list[CoachDashboardStudentItem]) -> list[CoachDashboardStudentItem]:
    def sort_key(item: CoachDashboardStudentItem) -> tuple:
        last_analysis_ts = (
            item.last_analysis_at.timestamp() if item.last_analysis_at else 0.0
        )
        return (
            -int(item.needs_response),
            -item.analyses_7d,
            -last_analysis_ts,
        )

    return sorted(items, key=sort_key)


async def build_list_dashboard(
    db: AsyncSession, *, coach_user_id: str
) -> CoachDashboardListResponse:
    now = _now()
    relations = await _load_active_relations(db, coach_user_id=coach_user_id)
    student_ids = [rel.student_user_id for rel, _ in relations]
    agg = await _aggregate_for_students(
        db, coach_user_id=coach_user_id, student_ids=student_ids, now=now
    )

    items: list[CoachDashboardStudentItem] = []
    for rel, user in relations:
        metrics = agg.get(rel.student_user_id, {})
        items.append(
            CoachDashboardStudentItem(
                student_user_id=rel.student_user_id,
                display_name=user.nickname or rel.student_user_id,
                avatar_url=user.avatar_url,
                relation_id=rel.id,
                analyses_7d=metrics.get("analyses_7d", 0),
                last_analysis_at=metrics.get("last_analysis_at"),
                last_annotation_at=metrics.get("last_annotation_at"),
                pending_tasks=metrics.get("pending_tasks", 0),
                needs_response=metrics.get("needs_response", False),
            )
        )

    sorted_items = _sort_students(items)
    return CoachDashboardListResponse(
        students=sorted_items,
        total=len(sorted_items),
        cached_at=dash_cache.stamp_cached_at(),
    )


async def get_list_dashboard(
    db: AsyncSession,
    redis: Redis | None,
    *,
    coach_user_id: str,
) -> CoachDashboardListResponse:
    ensure_coach_dashboard_enabled()
    cached = await dash_cache.get_list_cache(redis, coach_user_id=coach_user_id)
    if cached is not None:
        return cached
    payload = await build_list_dashboard(db, coach_user_id=coach_user_id)
    await dash_cache.set_list_cache(redis, coach_user_id=coach_user_id, payload=payload)
    return payload


async def build_student_dashboard(
    db: AsyncSession,
    *,
    coach: User,
    student_user_id: str,
) -> CoachDashboardDetailResponse:
    now = _now()
    relation = await require_active_relation(
        db, coach=coach, student_id=student_user_id
    )
    user = await db.get(User, student_user_id)
    if user is None:
        raise NotFoundError(code=40404, message="学员不存在")

    agg = await _aggregate_for_students(
        db,
        coach_user_id=coach.id,
        student_ids=[student_user_id],
        now=now,
    )
    metrics = agg.get(student_user_id, {})

    recent_analyses_rows = await db.execute(
        select(SwingAnalysis)
        .where(
            SwingAnalysis.user_id == student_user_id,
            SwingAnalysis.deleted_at.is_(None),
        )
        .order_by(SwingAnalysis.created_at.desc())
        .limit(RECENT_ANALYSES_LIMIT)
    )
    recent_analyses = [
        CoachDashboardAnalysisBrief(
            id=row.id,
            created_at=row.created_at,
            overall_score=row.overall_score,
            club_type=row.club_type,
            status=row.status,
        )
        for row in recent_analyses_rows.scalars().all()
    ]

    recent_ann_rows = await db.execute(
        select(AnalysisAnnotation)
        .where(
            AnalysisAnnotation.coach_user_id == coach.id,
            AnalysisAnnotation.student_user_id == student_user_id,
        )
        .order_by(AnalysisAnnotation.created_at.desc())
        .limit(RECENT_ANNOTATIONS_LIMIT)
    )
    recent_annotations = [
        CoachDashboardAnnotationBrief(
            id=row.id,
            annotation_type=row.annotation_type,
            text_content=row.text_content,
            created_at=row.created_at,
        )
        for row in recent_ann_rows.scalars().all()
    ]

    pending_task_rows = await db.execute(
        select(CoachAssignedTask, Drill.name)
        .outerjoin(Drill, Drill.id == CoachAssignedTask.drill_id)
        .where(
            CoachAssignedTask.coach_user_id == coach.id,
            CoachAssignedTask.student_user_id == student_user_id,
            CoachAssignedTask.status.in_(("assigned", "started")),
        )
        .order_by(CoachAssignedTask.created_at.desc())
    )
    pending_coach_tasks = [
        CoachDashboardTaskBrief(
            id=task.id,
            drill_name=drill_name,
            target_count=task.target_count,
            status=task.status,
            created_at=task.created_at,
        )
        for task, drill_name in pending_task_rows.all()
    ]

    return CoachDashboardDetailResponse(
        student_user_id=student_user_id,
        display_name=user.nickname or student_user_id,
        avatar_url=user.avatar_url,
        relation_id=relation.id,
        analyses_7d=metrics.get("analyses_7d", 0),
        last_analysis_at=metrics.get("last_analysis_at"),
        last_annotation_at=metrics.get("last_annotation_at"),
        pending_tasks=metrics.get("pending_tasks", 0),
        needs_response=metrics.get("needs_response", False),
        recent_analyses=recent_analyses,
        recent_annotations=recent_annotations,
        pending_coach_tasks=pending_coach_tasks,
        cached_at=dash_cache.stamp_cached_at(),
    )


async def get_student_dashboard(
    db: AsyncSession,
    redis: Redis | None,
    *,
    coach: User,
    student_user_id: str,
) -> CoachDashboardDetailResponse:
    ensure_coach_dashboard_enabled()
    cached = await dash_cache.get_detail_cache(
        redis, coach_user_id=coach.id, student_user_id=student_user_id
    )
    if cached is not None:
        return cached
    try:
        payload = await build_student_dashboard(
            db, coach=coach, student_user_id=student_user_id
        )
    except CoachStudentRelationError:
        raise
    await dash_cache.set_detail_cache(
        redis,
        coach_user_id=coach.id,
        student_user_id=student_user_id,
        payload=payload,
    )
    return payload


async def invalidate_dashboard_for_coach(
    *, coach_user_id: str, student_user_id: str | None = None
) -> None:
    try:
        from app.core.redis import get_redis

        redis = await get_redis()
        await dash_cache.invalidate_coach_dashboard(
            redis, coach_user_id=coach_user_id, student_user_id=student_user_id
        )
    except Exception:
        logger.warning("coach_dashboard_invalidate_skipped", exc_info=True)


__all__ = [
    "build_list_dashboard",
    "build_student_dashboard",
    "ensure_coach_dashboard_enabled",
    "get_list_dashboard",
    "get_student_dashboard",
    "invalidate_coach_dashboard",
    "invalidate_dashboard_for_coach",
]

invalidate_coach_dashboard = dash_cache.invalidate_coach_dashboard
