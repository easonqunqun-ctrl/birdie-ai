"""M8-03 · 教练-学员双向 opt-in 绑定 service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    BadRequestError,
    CoachStudentFieldNotVisibleError,
    CoachStudentRelationError,
    NotFoundError,
)
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.coach import CoachProfile, CoachStudentRelation
from app.models.user import User
from app.schemas.coach_student import (
    DEFAULT_VISIBILITY_PAYLOAD,
    VISIBILITY_FIELD_KEYS,
    CoachStudentInviteRequest,
    CoachStudentListResponse,
    CoachStudentRelationRead,
    CoachStudentSharedFieldResponse,
    CoachStudentUserBrief,
    CoachStudentVisibilityUpdate,
    StudentCoachOverviewResponse,
)
from app.services import user_profile_v2_service as profile_v2_svc
from app.services.coach_course_service import assert_coach_course_author, coach_course_user_ids
from app.services.user_service import get_user_by_id, get_user_by_invite_code

logger = get_logger("coach_student")

ACTIVE_LIKE_STATUSES = ("pending", "active", "paused")
PENDING_INVITE_TTL_DAYS = 60


def ensure_coach_module_enabled() -> None:
    if not settings.PHASE2_COACH_ENABLED:
        raise NotFoundError(code=40406, message="教练功能未开放")


def _merge_visibility(payload: dict | None) -> dict[str, bool]:
    merged = dict(DEFAULT_VISIBILITY_PAYLOAD)
    if payload:
        for key in VISIBILITY_FIELD_KEYS:
            if key in payload:
                merged[key] = bool(payload[key])
    # injuries 永不对教练开放（PIPL / kickoff R-01）
    merged["injuries"] = False
    return merged


async def expire_stale_pending_invitations(db: AsyncSession) -> int:
    """pending 超过 60 天未响应 → ended（kickoff §3.3）."""

    cutoff = datetime.now(UTC) - timedelta(days=PENDING_INVITE_TTL_DAYS)
    rows = (
        await db.execute(
            select(CoachStudentRelation).where(
                CoachStudentRelation.status == "pending",
                CoachStudentRelation.invited_at < cutoff,
            )
        )
    ).scalars().all()
    if not rows:
        return 0
    now = datetime.now(UTC)
    for relation in rows:
        relation.status = "ended"
        relation.ended_at = now
        relation.ended_by_user_id = None
    await db.flush()
    logger.info("coach_student_pending_expired", count=len(rows))
    return len(rows)


async def _build_shared_field_value(
    db: AsyncSession, *, student_id: str, field: str
) -> object | None:
    user = await get_user_by_id(db, student_id)
    profile = await profile_v2_svc.get_profile(db, student_id)

    if field == "handicap":
        data: dict[str, object] = {}
        if profile:
            if profile.handicap_official is not None:
                data["handicap_official"] = float(profile.handicap_official)
            if profile.handicap_self is not None:
                data["handicap_self"] = float(profile.handicap_self)
            if profile.handicap_source:
                data["handicap_source"] = profile.handicap_source
        if user.golf_level:
            data["golf_level"] = user.golf_level
        return data or None

    if field == "body":
        if profile is None:
            return None
        body = {
            key: getattr(profile, key)
            for key in ("height_cm", "weight_kg", "handedness")
            if getattr(profile, key) is not None
        }
        return body or None

    if field == "injuries":
        raise CoachStudentFieldNotVisibleError()

    if field == "goals":
        goals: dict[str, object] = {}
        if user.primary_goals:
            goals["primary_goals"] = list(user.primary_goals)
        if profile and profile.mid_long_goals:
            goals["mid_long_goals"] = list(profile.mid_long_goals)
        return goals or None

    if field == "training_preference":
        if profile is None:
            return None
        pref: dict[str, object] = {}
        if profile.training_preference:
            pref["training_preference"] = profile.training_preference
        if profile.training_preference_meta:
            pref["training_preference_meta"] = dict(profile.training_preference_meta)
        if profile.weekly_target_sessions is not None:
            pref["weekly_target_sessions"] = profile.weekly_target_sessions
        return pref or None

    if field == "frequent_venues":
        venues, _missing = await profile_v2_svc.list_favorite_venues(db, user_id=student_id)
        return [
            {
                "id": venue.id,
                "name": venue.name,
                "city": venue.city,
                "venue_type": venue.venue_type,
            }
            for venue in venues
        ]

    raise BadRequestError(code=40002, message="不支持的字段")


def _user_brief(user: User, *, display_name: str | None = None) -> CoachStudentUserBrief:
    return CoachStudentUserBrief(
        user_id=user.id,
        nickname=user.nickname,
        display_name=display_name,
    )


async def _coach_display_name(db: AsyncSession, coach_user_id: str) -> str | None:
    row = await db.execute(
        select(CoachProfile.display_name).where(CoachProfile.user_id == coach_user_id)
    )
    return row.scalar_one_or_none()


async def _serialize_relation(
    db: AsyncSession,
    relation: CoachStudentRelation,
    *,
    include_coach: bool = False,
    include_student: bool = False,
) -> CoachStudentRelationRead:
    coach = None
    student = None
    if include_coach:
        coach_user = await get_user_by_id(db, relation.coach_user_id)
        display = await _coach_display_name(db, relation.coach_user_id)
        coach = _user_brief(coach_user, display_name=display)
    if include_student:
        student_user = await get_user_by_id(db, relation.student_user_id)
        student = _user_brief(student_user)
    return CoachStudentRelationRead(
        id=relation.id,
        coach_user_id=relation.coach_user_id,
        student_user_id=relation.student_user_id,
        status=relation.status,
        visibility_payload=_merge_visibility(relation.visibility_payload),
        invited_at=relation.invited_at,
        invite_message=relation.invite_message,
        accepted_at=relation.accepted_at,
        ended_at=relation.ended_at,
        coach=coach,
        student=student,
    )


async def _assert_coach_can_manage(db: AsyncSession, *, coach: User) -> None:
    if coach.id in coach_course_user_ids():
        return
    if settings.PHASE2_COACH_ENABLED:
        from app.services.coach_profile_service import assert_active_coach

        await assert_active_coach(db, user=coach)
        return
    assert_coach_course_author(coach)


async def _resolve_student_id(
    db: AsyncSession,
    *,
    student_user_id: str | None,
    invite_code: str | None,
) -> str:
    if student_user_id and invite_code:
        raise BadRequestError(code=40001, message="student_user_id 与 invite_code 只能二选一")
    if not student_user_id and not invite_code:
        raise BadRequestError(code=40001, message="请提供 student_user_id 或 invite_code")
    if student_user_id:
        await get_user_by_id(db, student_user_id)
        return student_user_id
    code = (invite_code or "").strip().upper()
    student = await get_user_by_invite_code(db, code)
    if student is None:
        raise NotFoundError(code=40401, message="用户不存在")
    return student.id


async def _assert_student_available(
    db: AsyncSession,
    *,
    student_user_id: str,
    exclude_relation_id: str | None = None,
) -> None:
    stmt = select(CoachStudentRelation.id).where(
        CoachStudentRelation.student_user_id == student_user_id,
        CoachStudentRelation.status.in_(("pending", "active")),
    )
    if exclude_relation_id:
        stmt = stmt.where(CoachStudentRelation.id != exclude_relation_id)
    row = await db.execute(stmt)
    if row.scalar_one_or_none() is not None:
        raise BadRequestError(code=40915, message="学员已有活跃教练")


async def _get_relation_for_user(
    db: AsyncSession, *, relation_id: str, user: User
) -> CoachStudentRelation:
    row = await db.execute(
        select(CoachStudentRelation).where(CoachStudentRelation.id == relation_id)
    )
    relation = row.scalar_one_or_none()
    if relation is None:
        raise CoachStudentRelationError()
    if user.id not in (relation.coach_user_id, relation.student_user_id):
        raise CoachStudentRelationError()
    return relation


async def require_active_relation(
    db: AsyncSession, *, coach: User, student_id: str
) -> CoachStudentRelation:
    """校验 active 师生关系；不存在或已结束则 40312."""

    await _assert_coach_can_manage(db, coach=coach)
    row = await db.execute(
        select(CoachStudentRelation).where(
            CoachStudentRelation.coach_user_id == coach.id,
            CoachStudentRelation.student_user_id == student_id,
            CoachStudentRelation.status == "active",
        )
    )
    relation = row.scalar_one_or_none()
    if relation is None:
        raise CoachStudentRelationError()
    return relation


async def invite_student(
    db: AsyncSession,
    *,
    coach: User,
    payload: CoachStudentInviteRequest,
) -> CoachStudentRelationRead:
    ensure_coach_module_enabled()
    await expire_stale_pending_invitations(db)
    await _assert_coach_can_manage(db, coach=coach)
    student_id = await _resolve_student_id(
        db,
        student_user_id=payload.student_user_id,
        invite_code=payload.invite_code,
    )
    if student_id == coach.id:
        raise BadRequestError(code=40001, message="不能邀请自己")
    await _assert_student_available(db, student_user_id=student_id)

    existing = await db.execute(
        select(CoachStudentRelation).where(
            CoachStudentRelation.coach_user_id == coach.id,
            CoachStudentRelation.student_user_id == student_id,
            CoachStudentRelation.status.in_(("pending", "active")),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise BadRequestError(code=40903, message="已存在待处理或进行中的邀请")

    now = datetime.now(UTC)
    relation = CoachStudentRelation(
        id=new_id("csr"),
        coach_user_id=coach.id,
        student_user_id=student_id,
        status="pending",
        visibility_payload=dict(DEFAULT_VISIBILITY_PAYLOAD),
        invited_at=now,
        invite_message=(payload.message or "").strip() or None,
    )
    db.add(relation)
    await db.flush()
    logger.info(
        "coach_student_invited",
        relation_id=relation.id,
        coach_user_id=coach.id,
        student_user_id=student_id,
    )
    return await _serialize_relation(db, relation, include_coach=True, include_student=True)


async def list_coach_students(
    db: AsyncSession,
    *,
    coach: User,
    status: str | None = None,
) -> CoachStudentListResponse:
    ensure_coach_module_enabled()
    await expire_stale_pending_invitations(db)
    await _assert_coach_can_manage(db, coach=coach)
    valid_statuses = {"pending", "active", "paused", "ended"}
    if status and status not in valid_statuses:
        raise BadRequestError(code=40002, message="不支持的 status 筛选")
    stmt = select(CoachStudentRelation).where(CoachStudentRelation.coach_user_id == coach.id)
    if status:
        stmt = stmt.where(CoachStudentRelation.status == status)
    stmt = stmt.order_by(CoachStudentRelation.invited_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        await _serialize_relation(db, row, include_student=True) for row in rows
    ]
    return CoachStudentListResponse(items=items, total=len(items))


async def get_student_coach_overview(
    db: AsyncSession, *, student: User
) -> StudentCoachOverviewResponse:
    ensure_coach_module_enabled()
    await expire_stale_pending_invitations(db)
    rows = (
        await db.execute(
            select(CoachStudentRelation)
            .where(CoachStudentRelation.student_user_id == student.id)
            .where(CoachStudentRelation.status.in_((*ACTIVE_LIKE_STATUSES, "ended")))
            .order_by(CoachStudentRelation.invited_at.desc())
        )
    ).scalars().all()

    pending: list[CoachStudentRelationRead] = []
    active: CoachStudentRelationRead | None = None
    paused: CoachStudentRelationRead | None = None
    for row in rows:
        item = await _serialize_relation(db, row, include_coach=True)
        if row.status == "pending":
            pending.append(item)
        elif row.status == "active" and active is None:
            active = item
        elif row.status == "paused" and paused is None:
            paused = item
    return StudentCoachOverviewResponse(pending=pending, active=active, paused=paused)


async def accept_relation(
    db: AsyncSession, *, student: User, relation_id: str
) -> CoachStudentRelationRead:
    ensure_coach_module_enabled()
    await expire_stale_pending_invitations(db)
    relation = await _get_relation_for_user(db, relation_id=relation_id, user=student)
    if relation.student_user_id != student.id:
        raise CoachStudentRelationError()
    if relation.status != "pending":
        raise BadRequestError(code=40903, message="邀请状态不允许接受")
    await _assert_student_available(
        db, student_user_id=student.id, exclude_relation_id=relation.id
    )
    relation.status = "active"
    relation.accepted_at = datetime.now(UTC)
    await db.flush()
    logger.info("coach_student_accepted", relation_id=relation.id)
    return await _serialize_relation(db, relation, include_coach=True)


async def reject_relation(
    db: AsyncSession, *, student: User, relation_id: str
) -> CoachStudentRelationRead:
    ensure_coach_module_enabled()
    relation = await _get_relation_for_user(db, relation_id=relation_id, user=student)
    if relation.student_user_id != student.id or relation.status != "pending":
        raise BadRequestError(code=40903, message="邀请状态不允许拒绝")
    relation.status = "ended"
    relation.ended_at = datetime.now(UTC)
    relation.ended_by_user_id = student.id
    await db.flush()
    return await _serialize_relation(db, relation, include_coach=True)


async def end_relation(
    db: AsyncSession, *, user: User, relation_id: str
) -> CoachStudentRelationRead:
    ensure_coach_module_enabled()
    relation = await _get_relation_for_user(db, relation_id=relation_id, user=user)
    if relation.status not in ("active", "paused", "pending"):
        raise CoachStudentRelationError()
    relation.status = "ended"
    relation.ended_at = datetime.now(UTC)
    relation.ended_by_user_id = user.id
    await db.flush()
    logger.info("coach_student_ended", relation_id=relation.id, by_user_id=user.id)
    return await _serialize_relation(
        db,
        relation,
        include_coach=user.id == relation.student_user_id,
        include_student=user.id == relation.coach_user_id,
    )


async def update_visibility(
    db: AsyncSession,
    *,
    student: User,
    relation_id: str,
    payload: CoachStudentVisibilityUpdate,
) -> CoachStudentRelationRead:
    ensure_coach_module_enabled()
    relation = await _get_relation_for_user(db, relation_id=relation_id, user=student)
    if relation.student_user_id != student.id:
        raise CoachStudentRelationError()
    if relation.status not in ("active", "paused"):
        raise CoachStudentRelationError()
    merged = _merge_visibility(relation.visibility_payload)
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("injuries"):
        raise BadRequestError(code=40010, message="伤病信息默认不可对教练开放")
    for key, value in updates.items():
        if key in VISIBILITY_FIELD_KEYS:
            merged[key] = bool(value)
    relation.visibility_payload = merged
    await db.flush()
    return await _serialize_relation(db, relation, include_coach=True)


async def get_shared_field_for_coach(
    db: AsyncSession,
    *,
    coach: User,
    student_id: str,
    field: str,
) -> CoachStudentSharedFieldResponse:
    ensure_coach_module_enabled()
    await _assert_coach_can_manage(db, coach=coach)
    if field not in VISIBILITY_FIELD_KEYS:
        raise BadRequestError(code=40002, message="不支持的字段")
    relation = await require_active_relation(db, coach=coach, student_id=student_id)
    visibility = _merge_visibility(relation.visibility_payload)
    if not visibility.get(field, False):
        raise CoachStudentFieldNotVisibleError()
    value = await _build_shared_field_value(db, student_id=student_id, field=field)
    return CoachStudentSharedFieldResponse(field=field, visible=True, value=value)


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
            CoachStudentRelation.status.in_(("pending", "active")),
        )
    )
    existing = row.scalar_one_or_none()
    now = datetime.now(UTC)
    if existing is not None:
        if existing.status != status:
            existing.status = status
            if status == "active" and existing.accepted_at is None:
                existing.accepted_at = now
            await db.flush()
        return existing

    relation = CoachStudentRelation(
        id=new_id("csr"),
        coach_user_id=coach_user_id,
        student_user_id=student_user_id,
        status=status,
        visibility_payload=dict(DEFAULT_VISIBILITY_PAYLOAD),
        invited_at=now,
        accepted_at=now if status == "active" else None,
    )
    db.add(relation)
    await db.flush()
    logger.info(
        "coach_student_relation_created",
        coach_user_id=coach_user_id,
        student_user_id=student_user_id,
    )
    return relation


__all__ = [
    "PENDING_INVITE_TTL_DAYS",
    "accept_relation",
    "end_relation",
    "ensure_coach_module_enabled",
    "ensure_relation",
    "expire_stale_pending_invitations",
    "get_shared_field_for_coach",
    "get_student_coach_overview",
    "invite_student",
    "list_coach_students",
    "reject_relation",
    "require_active_relation",
    "update_visibility",
]
