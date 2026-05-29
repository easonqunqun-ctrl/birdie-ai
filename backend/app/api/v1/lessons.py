"""P2-M11-04 · 阶段考核写端点.

- ``POST /v1/lessons/{lesson_id}/attempt`` — 提交 swing_analysis 参与课时考核
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.assessment import LessonAttemptRequest, LessonAttemptResponse
from app.schemas.base import APIResponse, ok
from app.schemas.course import CertificateDetailRead
from app.services import course_certificate_service as cert_svc
from app.services import course_service

router = APIRouter()


def _ensure_courses_enabled() -> None:
    if not settings.PHASE2_COURSES_ENABLED:
        raise NotFoundError(code=40406, message="课程功能未开放")


@router.post(
    "/{lesson_id}/attempt",
    summary="提交阶段考核（M11-04）",
    response_model=APIResponse[LessonAttemptResponse],
)
async def submit_lesson_attempt(
    lesson_id: str,
    payload: LessonAttemptRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用已完成 swing_analysis 参与 engine_score 考核，更新 user_course_progress."""

    _ensure_courses_enabled()
    outcome, stage_upgraded, upgraded_to_stage, issued_cert = (
        await course_service.submit_lesson_attempt(
            db,
            user_id=user.id,
            lesson_id=lesson_id,
            swing_analysis_id=payload.swing_analysis_id,
        )
    )
    certificate: CertificateDetailRead | None = None
    if issued_cert is not None:
        item = cert_svc.certificate_to_read_dict(
            issued_cert,
            course_title=(issued_cert.extra_metadata or {}).get("course_title", ""),
            holder_name=(issued_cert.extra_metadata or {}).get("holder_name"),
        )
        if not item["course_title"]:
            course = await course_service.get_course(db, issued_cert.course_id)
            if course is not None:
                item = cert_svc.certificate_to_read_dict(
                    issued_cert,
                    course_title=course.title,
                    holder_name=item["holder_name"],
                )
        certificate = CertificateDetailRead(**item)
    await db.commit()
    return ok(
        LessonAttemptResponse(
            passed=outcome.passed,
            score=outcome.score,
            min_score=outcome.min_score,
            attempts_used=outcome.attempts_used,
            max_attempts=outcome.max_attempts,
            failure_reason=outcome.failure_reason,  # type: ignore[arg-type]
            feedback=outcome.feedback,
            stage_upgraded=stage_upgraded,
            upgraded_to_stage=upgraded_to_stage,
            certificate=certificate,
        )
    )
