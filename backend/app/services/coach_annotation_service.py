"""M8-04 / M12-09 · 教练报告批注 service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.models.coach import AnalysisAnnotation
from app.models.pro_library import ProPlayer, ProSwingClip
from app.models.user import User
from app.schemas.coach_annotation import CoachAnnotationClipRefRead, CoachAnnotationCreate
from app.schemas.pro_library import ProPlayerRead, ProSwingClipRead
from app.services import pro_library_service
from app.services.coach_course_service import assert_coach_course_author, coach_course_user_ids
from app.services.coach_student_service import require_active_relation

logger = get_logger("coach_annotation")

TEXT_CONTENT_MAX_LEN = 500


def ensure_coach_annotations_enabled() -> None:
    if not settings.PHASE2_COACH_ANNOTATIONS_ENABLED:
        raise NotFoundError(code=40406, message="教练批注功能未开放")


async def _assert_coach_can_manage(db: AsyncSession, *, coach: User) -> None:
    if coach.id in coach_course_user_ids():
        return
    if settings.PHASE2_COACH_ENABLED:
        from app.services.coach_profile_service import assert_active_coach

        await assert_active_coach(db, user=coach)
        return
    assert_coach_course_author(coach)


async def _get_analysis(db: AsyncSession, *, analysis_id: str) -> SwingAnalysis:
    row = await db.execute(
        select(SwingAnalysis).where(
            SwingAnalysis.id == analysis_id,
            SwingAnalysis.deleted_at.is_(None),
        )
    )
    analysis = row.scalar_one_or_none()
    if analysis is None:
        raise NotFoundError(code=40404, message="分析报告不存在")
    if analysis.is_sample:
        raise BadRequestError(code=40093, message="示例分析报告不可批注")
    if analysis.status != "completed":
        raise BadRequestError(code=40001, message="仅已完成分析可批注")
    return analysis


async def _assert_coach_can_annotate_analysis(
    db: AsyncSession, *, coach: User, analysis: SwingAnalysis
) -> None:
    await _assert_coach_can_manage(db, coach=coach)
    await require_active_relation(db, coach=coach, student_id=analysis.user_id)


async def _resolve_clip_ref(
    db: AsyncSession, clip_id: str | None
) -> tuple[ProSwingClip | None, ProPlayer | None, bool]:
    if not clip_id:
        return None, None, False
    clip = await pro_library_service.get_clip(db, clip_id)
    if clip is None or not clip.is_published:
        return None, None, True
    player = await pro_library_service.get_player(db, clip.pro_player_id)
    if player is None or not player.is_active:
        return None, None, True
    return clip, player, False


def _normalize_text_content(raw: str | None) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if len(text) > TEXT_CONTENT_MAX_LEN:
        raise BadRequestError(code=40001, message=f"文字批注不超过 {TEXT_CONTENT_MAX_LEN} 字")
    return text


def _to_clip_ref_read(
    ann: AnalysisAnnotation,
    clip: ProSwingClip | None,
    player: ProPlayer | None,
    *,
    clip_unavailable: bool,
) -> CoachAnnotationClipRefRead:
    return CoachAnnotationClipRefRead(
        id=ann.id,
        analysis_id=ann.analysis_id,
        annotation_type=ann.annotation_type,  # type: ignore[arg-type]
        pro_clip_id=ann.pro_clip_id,
        text_content=ann.text_content,
        audit_status=ann.audit_status,
        is_visible=ann.is_visible,
        created_at=ann.created_at,
        clip=ProSwingClipRead.model_validate(clip) if clip else None,
        player=ProPlayerRead.model_validate(player) if player else None,
        clip_unavailable=clip_unavailable,
    )


async def create_annotation(
    db: AsyncSession,
    *,
    coach: User,
    analysis_id: str,
    payload: CoachAnnotationCreate,
) -> CoachAnnotationClipRefRead:
    ensure_coach_annotations_enabled()
    analysis = await _get_analysis(db, analysis_id=analysis_id)
    await _assert_coach_can_annotate_analysis(db, coach=coach, analysis=analysis)

    if payload.annotation_type == "video_ref":
        if not settings.PHASE2_PROS_ENABLED:
            raise NotFoundError(code=40406, message="球手对比库未开放")
        if not payload.pro_clip_id:
            raise BadRequestError(code=40001, message="video_ref 须提供 pro_clip_id")
        clip, player, unavailable = await _resolve_clip_ref(db, payload.pro_clip_id)
        if unavailable or clip is None:
            raise NotFoundError(code=40406, message="职业镜头不存在或已下架")
        text_content = _normalize_text_content(payload.text_content)
        ann = AnalysisAnnotation(
            id=new_id("can"),
            coach_user_id=coach.id,
            student_user_id=analysis.user_id,
            analysis_id=analysis.id,
            annotation_type="video_ref",
            pro_clip_id=clip.id,
            text_content=text_content,
            audit_status="approved",
            is_visible=True,
        )
        db.add(ann)
        await db.flush()
        if text_content:
            from app.services.content_moderation_service import moderate_annotation_text

            await moderate_annotation_text(db, annotation=ann, text=text_content)
        logger.info(
            "coach_annotation_created",
            annotation_id=ann.id,
            analysis_id=analysis.id,
            annotation_type="video_ref",
            clip_id=clip.id,
            coach_id=coach.id,
        )
        from app.services.coach_dashboard_service import invalidate_dashboard_for_coach

        await invalidate_dashboard_for_coach(
            coach_user_id=coach.id, student_user_id=analysis.user_id
        )
        return _to_clip_ref_read(ann, clip, player, clip_unavailable=False)

    if payload.annotation_type == "text":
        text_content = _normalize_text_content(payload.text_content)
        if text_content is None:
            raise BadRequestError(code=40001, message="文字批注不能为空")
        ann = AnalysisAnnotation(
            id=new_id("can"),
            coach_user_id=coach.id,
            student_user_id=analysis.user_id,
            analysis_id=analysis.id,
            annotation_type="text",
            pro_clip_id=None,
            text_content=text_content,
            audit_status="pending",
            is_visible=False,
        )
        db.add(ann)
        await db.flush()
        from app.services.content_moderation_service import moderate_annotation_text

        await moderate_annotation_text(db, annotation=ann, text=text_content)
        logger.info(
            "coach_annotation_created",
            annotation_id=ann.id,
            analysis_id=analysis.id,
            annotation_type="text",
            coach_id=coach.id,
        )
        from app.services.coach_dashboard_service import invalidate_dashboard_for_coach

        await invalidate_dashboard_for_coach(
            coach_user_id=coach.id, student_user_id=analysis.user_id
        )
        return _to_clip_ref_read(ann, None, None, clip_unavailable=False)

    raise BadRequestError(code=40001, message="当前仅支持 text / video_ref 批注")


async def list_coach_annotations(
    db: AsyncSession,
    *,
    coach: User,
    analysis_id: str,
) -> list[CoachAnnotationClipRefRead]:
    ensure_coach_annotations_enabled()
    analysis = await _get_analysis(db, analysis_id=analysis_id)
    await _assert_coach_can_annotate_analysis(db, coach=coach, analysis=analysis)

    rows = await db.execute(
        select(AnalysisAnnotation)
        .where(
            AnalysisAnnotation.analysis_id == analysis_id,
            AnalysisAnnotation.coach_user_id == coach.id,
        )
        .order_by(AnalysisAnnotation.created_at.desc())
    )
    out: list[CoachAnnotationClipRefRead] = []
    for ann in rows.scalars().all():
        clip, player, unavailable = await _resolve_clip_ref(db, ann.pro_clip_id)
        out.append(_to_clip_ref_read(ann, clip, player, clip_unavailable=unavailable))
    return out


async def list_student_annotations(
    db: AsyncSession,
    *,
    student: User,
    analysis_id: str,
) -> list[CoachAnnotationClipRefRead]:
    ensure_coach_annotations_enabled()
    analysis = await _get_analysis(db, analysis_id=analysis_id)
    if analysis.user_id != student.id:
        raise ForbiddenError(code=40301, message="无权查看该分析")

    rows = await db.execute(
        select(AnalysisAnnotation).where(
            AnalysisAnnotation.analysis_id == analysis_id,
            AnalysisAnnotation.is_visible.is_(True),
            AnalysisAnnotation.audit_status == "approved",
        ).order_by(AnalysisAnnotation.created_at.desc())
    )
    out: list[CoachAnnotationClipRefRead] = []
    for ann in rows.scalars().all():
        clip, player, unavailable = await _resolve_clip_ref(db, ann.pro_clip_id)
        out.append(_to_clip_ref_read(ann, clip, player, clip_unavailable=unavailable))
    return out


async def delete_annotation(
    db: AsyncSession,
    *,
    coach: User,
    annotation_id: str,
) -> None:
    ensure_coach_annotations_enabled()
    await _assert_coach_can_manage(db, coach=coach)
    row = await db.execute(
        select(AnalysisAnnotation).where(AnalysisAnnotation.id == annotation_id)
    )
    ann = row.scalar_one_or_none()
    if ann is None:
        raise NotFoundError(code=40404, message="批注不存在")
    if ann.coach_user_id != coach.id:
        raise ForbiddenError(code=40301, message="无权删除该批注")
    analysis = await _get_analysis(db, analysis_id=ann.analysis_id)
    await require_active_relation(db, coach=coach, student_id=analysis.user_id)
    await db.delete(ann)


def can_user_coach_annotate(user: User) -> bool:
    if not settings.PHASE2_COACH_ANNOTATIONS_ENABLED:
        return False
    return user.id in coach_course_user_ids()


__all__ = [
    "can_user_coach_annotate",
    "create_annotation",
    "delete_annotation",
    "ensure_coach_annotations_enabled",
    "list_coach_annotations",
    "list_student_annotations",
]
