"""P2-M11-05 · 用户课程证书 / 阶段勋章读端点."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.courses import _ensure_courses_enabled
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.course import CertificateDetailRead, UserCourseStageRead
from app.services import course_certificate_service as cert_svc
from app.services import course_service

router = APIRouter()


@router.get(
    "/course-stage",
    summary="当前学习阶段与已获证书（M11-05）",
    response_model=APIResponse[UserCourseStageRead],
)
async def get_my_course_stage(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_courses_enabled()
    current_stage = await course_service.current_user_stage(db, user.id)
    certificates = await cert_svc.list_user_certificates(db, user.id)
    earned_stages = sorted({item["stage"] for item in certificates})
    return ok(
        UserCourseStageRead(
            current_stage=current_stage,
            earned_stages=earned_stages,
            certificates=[CertificateDetailRead(**item) for item in certificates],
        )
    )


@router.get(
    "/certificates",
    summary="列出我的通关证书（M11-05）",
    response_model=APIResponse[list[CertificateDetailRead]],
)
async def list_my_certificates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_courses_enabled()
    items = await cert_svc.list_user_certificates(db, user.id)
    return ok([CertificateDetailRead(**item) for item in items])


@router.get(
    "/certificates/{cert_id}",
    summary="获取单张证书详情（M11-05）",
    response_model=APIResponse[CertificateDetailRead],
)
async def get_my_certificate(
    cert_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_courses_enabled()
    item = await cert_svc.get_user_certificate(db, user_id=user.id, cert_id=cert_id)
    return ok(CertificateDetailRead(**item))
