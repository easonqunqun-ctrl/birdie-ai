"""M8-08 · 教练 UGC 内容审核 orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.coach import AnalysisAnnotation
from app.models.moderation import ModerationQueue
from app.models.user import User
from app.schemas.moderation import (
    ModerationQueueItemRead,
    ModerationQueueListResponse,
    ModerationQueueReviewRequest,
)
from app.services.coach_profile_service import assert_admin
from app.services.content_safety_service import (
    ModerationDecision,
    ModerationOutcome,
    moderate_text,
)

logger = get_logger("content_moderation")

TARGET_ANNOTATIONS = "analysis_annotations"
TARGET_COACH_TASKS = "coach_assigned_tasks"


def is_coach_content_moderation_enabled() -> bool:
    return settings.PHASE2_COACH_CONTENT_MODERATION_ENABLED


def _sla_deadline() -> datetime:
    return datetime.now(UTC) + timedelta(hours=settings.CONTENT_MODERATION_SLA_HOURS)


async def _upsert_queue_row(
    db: AsyncSession,
    *,
    target_table: str,
    target_id: str,
    media_type: str,
    text_snapshot: str | None,
    media_url: str | None,
    outcome: ModerationOutcome,
    needs_manual: bool,
) -> ModerationQueue:
    existing = await db.execute(
        select(ModerationQueue)
        .where(
            ModerationQueue.target_table == target_table,
            ModerationQueue.target_id == target_id,
            ModerationQueue.reviewed_at.is_(None),
        )
        .order_by(ModerationQueue.created_at.desc())
        .limit(1)
    )
    row = existing.scalar_one_or_none()
    if row is None:
        row = ModerationQueue(
            id=new_id("modq"),
            target_table=target_table,
            target_id=target_id,
            media_type=media_type,
            media_url=media_url,
            text_snapshot=text_snapshot,
            sla_deadline_at=_sla_deadline(),
        )
        db.add(row)
    row.ai_risk_label = outcome.risk_label
    row.ai_risk_score = outcome.risk_score
    row.ai_decision = outcome.decision.value
    if needs_manual:
        row.reviewed_at = None
        row.reviewer_action = None
    await db.flush()
    return row


def _apply_annotation_status(ann: AnalysisAnnotation, decision: ModerationDecision) -> None:
    if decision == ModerationDecision.APPROVED:
        ann.audit_status = "approved"
        ann.is_visible = True
        return
    if decision == ModerationDecision.REJECTED:
        ann.audit_status = "rejected"
        ann.is_visible = False
        return
    if decision == ModerationDecision.MANUAL_REVIEW:
        ann.audit_status = "manual_review"
        ann.is_visible = False
        return
    ann.audit_status = "pending"
    ann.is_visible = False


async def moderate_annotation_text(
    db: AsyncSession,
    *,
    annotation: AnalysisAnnotation,
    text: str,
) -> ModerationOutcome:
    if not is_coach_content_moderation_enabled():
        _apply_annotation_status(annotation, ModerationDecision.APPROVED)
        return ModerationOutcome(decision=ModerationDecision.APPROVED)

    _apply_annotation_status(annotation, ModerationDecision.PENDING)
    outcome = await moderate_text(text)
    needs_manual = outcome.decision in {
        ModerationDecision.MANUAL_REVIEW,
        ModerationDecision.PENDING,
    }
    if needs_manual or outcome.decision == ModerationDecision.REJECTED:
        await _upsert_queue_row(
            db,
            target_table=TARGET_ANNOTATIONS,
            target_id=annotation.id,
            media_type="text",
            text_snapshot=text,
            media_url=None,
            outcome=outcome,
            needs_manual=needs_manual,
        )
    if outcome.provider_error:
        logger.warning("content_moderation_provider_error", target_id=annotation.id)
    _apply_annotation_status(annotation, outcome.decision)
    await db.flush()
    return outcome


async def moderate_coach_task_note(
    db: AsyncSession,
    *,
    assigned_id: str,
    coach_note: str,
) -> ModerationOutcome:
    if not is_coach_content_moderation_enabled():
        return ModerationOutcome(decision=ModerationDecision.APPROVED)

    outcome = await moderate_text(coach_note)
    needs_manual = outcome.decision in {
        ModerationDecision.MANUAL_REVIEW,
        ModerationDecision.PENDING,
    }
    if needs_manual or outcome.decision == ModerationDecision.REJECTED:
        await _upsert_queue_row(
            db,
            target_table=TARGET_COACH_TASKS,
            target_id=assigned_id,
            media_type="text",
            text_snapshot=coach_note,
            media_url=None,
            outcome=outcome,
            needs_manual=needs_manual,
        )
    if outcome.provider_error:
        logger.warning("content_moderation_provider_error", target_id=assigned_id)
    await db.flush()
    return outcome


async def is_coach_note_visible_to_student(
    db: AsyncSession, *, assigned_id: str, coach_note: str | None
) -> bool:
    if not coach_note:
        return False
    if not is_coach_content_moderation_enabled():
        return True
    status = await get_target_publication_status(
        db, target_table=TARGET_COACH_TASKS, target_id=assigned_id
    )
    return status == "approved"


async def get_target_publication_status(
    db: AsyncSession, *, target_table: str, target_id: str
) -> str:
    if not is_coach_content_moderation_enabled():
        return "approved"
    row = await db.execute(
        select(ModerationQueue)
        .where(
            ModerationQueue.target_table == target_table,
            ModerationQueue.target_id == target_id,
        )
        .order_by(ModerationQueue.created_at.desc())
        .limit(1)
    )
    item = row.scalar_one_or_none()
    if item is None:
        return "approved"
    if item.reviewer_action == "approve":
        return "approved"
    if item.reviewer_action == "reject":
        return "rejected"
    return item.ai_decision or "pending"


async def list_pending_for_admin(
    db: AsyncSession,
    *,
    admin: User,
    limit: int = 50,
) -> ModerationQueueListResponse:
    assert_admin(admin)
    total = await db.scalar(
        select(func.count())
        .select_from(ModerationQueue)
        .where(ModerationQueue.reviewed_at.is_(None))
    )
    rows = await db.execute(
        select(ModerationQueue)
        .where(ModerationQueue.reviewed_at.is_(None))
        .order_by(ModerationQueue.sla_deadline_at.asc())
        .limit(limit)
    )
    items = [
        ModerationQueueItemRead.model_validate(row) for row in rows.scalars().all()
    ]
    return ModerationQueueListResponse(items=items, total=int(total or 0))


async def review_queue_item(
    db: AsyncSession,
    *,
    admin: User,
    queue_id: str,
    payload: ModerationQueueReviewRequest,
) -> ModerationQueueItemRead:
    assert_admin(admin)
    row = await db.get(ModerationQueue, queue_id)
    if row is None:
        raise NotFoundError(code=40404, message="审核队列项不存在")
    if row.reviewed_at is not None:
        raise BadRequestError(code=40001, message="该队列项已处理")

    row.reviewer_user_id = admin.id
    row.reviewer_action = payload.action
    row.reviewer_note = (payload.note or "").strip() or None
    row.reviewed_at = datetime.now(UTC)

    if row.target_table == TARGET_ANNOTATIONS:
        ann = await db.get(AnalysisAnnotation, row.target_id)
        if ann is not None:
            if payload.action == "approve":
                ann.audit_status = "approved"
                ann.is_visible = True
            else:
                ann.audit_status = "rejected"
                ann.is_visible = False

    await db.flush()
    return ModerationQueueItemRead.model_validate(row)
