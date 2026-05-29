"""M8-07 · 教练教学报告 service."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.security import new_id
from app.integrations.llm import AbstractLLMClient, get_llm_client
from app.integrations.minio import MinioStorageClient
from app.models.analysis import SwingAnalysis
from app.models.coach import CourseSessionRecap
from app.models.user import User
from app.schemas.coach_recap import (
    CoachRecapCreateRequest,
    CoachRecapCreateResponse,
    CoachRecapExportPdfResponse,
    CoachRecapListItem,
    CoachRecapListResponse,
)
from app.services.coach_student_service import require_active_relation
from app.services.llm.coach_recap_prompt import (
    RecapIssueBrief,
    RecapStudentContext,
    build_fallback_summary,
    build_recap_messages,
    summary_passes_quality_gate,
)
from app.services.pdf.recap_pdf import build_watermark_line, render_recap_pdf

RECAP_LLM_TIMEOUT_SECONDS = 15


def ensure_coach_recap_enabled() -> None:
    if not settings.PHASE2_COACH_RECAP_ENABLED:
        raise NotFoundError(code=40406, message="教练教学报告未开放")


async def _load_student_contexts(
    db: AsyncSession,
    *,
    coach: User,
    student_ids: list[str],
    analysis_ids: list[str],
) -> list[RecapStudentContext]:
    unique_students = list(dict.fromkeys(student_ids))
    for sid in unique_students:
        await require_active_relation(db, coach=coach, student_id=sid)

    rows = await db.execute(
        select(SwingAnalysis, User)
        .join(User, User.id == SwingAnalysis.user_id)
        .options(selectinload(SwingAnalysis.issues))
        .where(
            SwingAnalysis.id.in_(analysis_ids),
            SwingAnalysis.deleted_at.is_(None),
            SwingAnalysis.status == "completed",
        )
    )
    analyses = rows.all()
    if len(analyses) != len(set(analysis_ids)):
        raise BadRequestError(code=40001, message="部分分析报告不存在或未完成")

    by_student: dict[str, RecapStudentContext] = {}
    for analysis, user in analyses:
        if analysis.user_id not in unique_students:
            raise ForbiddenError(code=40312, message="分析报告不属于所选学员")
        issues = [
            RecapIssueBrief(
                name=issue.name,
                issue_type=issue.issue_type,
                severity=issue.severity,
                score=int(issue.confidence * 100) if issue.confidence is not None else None,
            )
            for issue in sorted(analysis.issues or [], key=lambda x: x.sort_order)
        ]
        ctx = RecapStudentContext(
            student_user_id=analysis.user_id,
            display_name=user.nickname or analysis.user_id,
            analysis_id=analysis.id,
            overall_score=analysis.overall_score,
            club_type=analysis.club_type,
            issues=issues,
        )
        by_student[analysis.user_id] = ctx

    missing = [sid for sid in unique_students if sid not in by_student]
    if missing:
        raise BadRequestError(code=40001, message="每位学员至少选择一份已完成分析报告")

    return [by_student[sid] for sid in unique_students if sid in by_student]


async def _complete_llm_summary(
    client: AbstractLLMClient,
    *,
    contexts: list[RecapStudentContext],
    session_date: str,
) -> tuple[str, str | None]:
    messages = build_recap_messages(contexts, session_date=session_date)
    chunks: list[str] = []
    error_msg: str | None = None
    async for chunk in client.stream_chat(messages, temperature=0.4, max_tokens=1200):
        if chunk.type == "content":
            chunks.append(chunk.delta)
        elif chunk.type == "error":
            error_msg = chunk.error or "LLM 调用失败"
            break
    text = "".join(chunks).strip()
    if error_msg or not text:
        return build_fallback_summary(contexts, session_date=session_date), None
    if not summary_passes_quality_gate(text, contexts):
        return build_fallback_summary(contexts, session_date=session_date), settings.LLM_MODEL
    return text, settings.LLM_MODEL


async def create_recap(
    db: AsyncSession,
    *,
    coach: User,
    payload: CoachRecapCreateRequest,
    llm_client: AbstractLLMClient | None = None,
) -> CoachRecapCreateResponse:
    ensure_coach_recap_enabled()
    contexts = await _load_student_contexts(
        db,
        coach=coach,
        student_ids=payload.student_ids,
        analysis_ids=payload.analysis_ids,
    )
    session_date_str = payload.session_date.isoformat()
    client = llm_client or get_llm_client()
    ai_summary, model_name = await _complete_llm_summary(
        client, contexts=contexts, session_date=session_date_str
    )
    recap = CourseSessionRecap(
        id=new_id("csr"),
        coach_user_id=coach.id,
        session_date=payload.session_date,
        student_ids=list(dict.fromkeys(payload.student_ids)),
        analysis_ids=list(dict.fromkeys(payload.analysis_ids)),
        ai_summary=ai_summary,
        ai_summary_model=model_name,
        coach_manual_notes=payload.coach_manual_notes,
        status="finalized",
    )
    db.add(recap)
    await db.flush()
    return CoachRecapCreateResponse(
        recap_id=recap.id,
        ai_summary=ai_summary,
        status=recap.status,
        ai_summary_model=model_name,
    )


def _resolve_pdf_url(
    storage: MinioStorageClient,
    recap: CourseSessionRecap,
) -> tuple[str | None, datetime | None]:
    if not recap.pdf_object_key:
        return None, None
    now = datetime.now(UTC)
    expires_at = recap.pdf_url_expires_at
    if expires_at is not None:
        exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        if exp <= now:
            return None, exp
    url, fresh_expires = storage.presign_get_url(
        recap.pdf_object_key,
        expires_in_seconds=settings.COACH_RECAP_PDF_URL_TTL_SECONDS,
    )
    return url, fresh_expires


async def export_recap_pdf(
    db: AsyncSession,
    *,
    coach: User,
    recap_id: str,
    storage: MinioStorageClient,
) -> CoachRecapExportPdfResponse:
    ensure_coach_recap_enabled()
    recap = await db.get(CourseSessionRecap, recap_id)
    if recap is None or recap.coach_user_id != coach.id:
        raise NotFoundError(code=40404, message="教学报告不存在")
    if not recap.ai_summary:
        raise BadRequestError(code=40001, message="请先生成 AI 汇总")

    coach_profile_name = coach.nickname or coach.id
    body = recap.ai_summary
    if recap.coach_manual_notes:
        body = f"{body}\n\n## 教练补充\n{recap.coach_manual_notes.strip()}"
    watermark = build_watermark_line(
        coach_display_name=coach_profile_name,
        coach_user_id=coach.id,
    )
    pdf_bytes = render_recap_pdf(
        title=f"教学报告 · {recap.session_date.isoformat()}",
        body_markdown=body,
        watermark_line=watermark,
    )
    key = f"coach-recap/{recap.id}.pdf"
    storage.put_object_bytes(key=key, data=pdf_bytes, content_type="application/pdf")
    _, expires_at = storage.presign_get_url(
        key, expires_in_seconds=settings.COACH_RECAP_PDF_URL_TTL_SECONDS
    )
    recap.pdf_object_key = key
    recap.pdf_url_expires_at = expires_at
    recap.status = "exported"
    await db.flush()
    pdf_url, _ = storage.presign_get_url(
        key, expires_in_seconds=settings.COACH_RECAP_PDF_URL_TTL_SECONDS
    )
    return CoachRecapExportPdfResponse(pdf_url=pdf_url, pdf_url_expires_at=expires_at)


async def list_recaps(
    db: AsyncSession,
    *,
    coach: User,
    page: int = 1,
    page_size: int = 20,
    storage: MinioStorageClient | None = None,
) -> CoachRecapListResponse:
    ensure_coach_recap_enabled()
    page = max(1, page)
    page_size = min(max(1, page_size), 50)
    offset = (page - 1) * page_size

    total = await db.scalar(
        select(func.count())
        .select_from(CourseSessionRecap)
        .where(CourseSessionRecap.coach_user_id == coach.id)
    )
    rows = await db.execute(
        select(CourseSessionRecap)
        .where(CourseSessionRecap.coach_user_id == coach.id)
        .order_by(CourseSessionRecap.session_date.desc(), CourseSessionRecap.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items: list[CoachRecapListItem] = []
    for recap in rows.scalars().all():
        pdf_url: str | None = None
        pdf_expires = recap.pdf_url_expires_at
        if storage is not None and recap.pdf_object_key:
            pdf_url, pdf_expires = _resolve_pdf_url(storage, recap)
        items.append(
            CoachRecapListItem(
                id=recap.id,
                session_date=recap.session_date,
                student_ids=list(recap.student_ids or []),
                analysis_ids=list(recap.analysis_ids or []),
                status=recap.status,
                ai_summary=recap.ai_summary,
                pdf_url=pdf_url,
                pdf_url_expires_at=pdf_expires,
                created_at=recap.created_at,
            )
        )
    return CoachRecapListResponse(items=items, total=int(total or 0))
