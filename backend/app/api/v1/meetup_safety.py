"""M13-09 · 约球合规 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.meetup_safety import (
    MeetupGenderPreferenceUpdate,
    MeetupSafetyStatus,
    MeetupSpectatorOptinUpdate,
    MeetupTosAccept,
    MeetupTosContent,
)
from app.services import meetup_safety_service as safety_svc

router = APIRouter()

MEETUP_TOS_BODY = (
    "平台仅提供球友信息匹配与活动组织工具，**不参与任何线下约球或挑战活动**，"
    "不对线下见面、练球、比赛过程中的人身安全、财产安全或纠纷承担任何责任。"
    "请勿在平台内交换手机号、微信号等联系方式；线下活动请选择公共场所并告知亲友。"
    "禁止以约球为名组织赌博、现金或实物对赌；违者将被限制功能并可能承担法律责任。"
)
MEETUP_TOS_DISCLAIMER = (
    "线下活动请确保人身与财产安全。拒绝即表示不使用约球相关功能。"
)


def _ensure_meetup_enabled() -> None:
    if not settings.PHASE2_MEETUP_ENABLED:
        raise NotFoundError(code=40406, message="约球功能未开放")


@router.get(
    "/safety/tos",
    summary="约球服务协议增量文本（M13-09）",
    response_model=APIResponse[MeetupTosContent],
)
async def get_meetup_tos_text(
    user: User = Depends(get_current_user),
):
    _ensure_meetup_enabled()
    return ok(
        MeetupTosContent(
            body=MEETUP_TOS_BODY,
            disclaimer=MEETUP_TOS_DISCLAIMER,
        )
    )


@router.get(
    "/safety/status",
    summary="约球合规状态（M13-09）",
    response_model=APIResponse[MeetupSafetyStatus],
)
async def get_meetup_safety_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_meetup_enabled()
    data = await safety_svc.get_safety_status(db, user=user)
    return ok(MeetupSafetyStatus.model_validate(data))


@router.post(
    "/safety/accept-tos",
    summary="同意约球服务协议（M13-09）",
    response_model=APIResponse[MeetupSafetyStatus],
)
async def accept_meetup_tos(
    payload: MeetupTosAccept | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_meetup_enabled()
    if settings.MEETUP_MOCK_IDENTITY_VERIFIED and settings.WECHAT_MOCK_LOGIN:
        safety_svc.maybe_stamp_mock_identity(user)
    data = await safety_svc.accept_meetup_tos(
        db,
        user=user,
        gender_preference=payload.gender_preference if payload else None,
    )
    await db.commit()
    return ok(MeetupSafetyStatus.model_validate(data))


@router.patch(
    "/safety/preferences",
    summary="更新约球匹配偏好（M13-09）",
    response_model=APIResponse[MeetupSafetyStatus],
)
async def update_meetup_preferences(
    payload: MeetupGenderPreferenceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_meetup_enabled()
    await safety_svc.ensure_meetup_access(db, user=user)
    data = await safety_svc.update_gender_preference(
        db, user=user, preference=payload.gender_preference
    )
    await db.commit()
    return ok(MeetupSafetyStatus.model_validate(data))


@router.patch(
    "/safety/spectator-optin",
    summary="学员授权教练旁观约球（M13-10）",
    response_model=APIResponse[MeetupSafetyStatus],
)
async def update_meetup_spectator_optin(
    payload: MeetupSpectatorOptinUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_meetup_enabled()
    data = await safety_svc.update_coach_spectator_optin(
        db, user=user, optin=payload.coach_spectator_optin
    )
    await db.commit()
    return ok(MeetupSafetyStatus.model_validate(data))


@router.post(
    "/safety/mock-identity",
    summary="mock 登录补齐实名（仅 WECHAT_MOCK_LOGIN）",
    response_model=APIResponse[MeetupSafetyStatus],
)
async def mock_meetup_identity(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_meetup_enabled()
    if not settings.WECHAT_MOCK_LOGIN:
        raise NotFoundError(code=40406, message="接口未开放")
    await safety_svc.stamp_mock_identity(db, user=user)
    await db.commit()
    data = await safety_svc.get_safety_status(db, user=user)
    return ok(MeetupSafetyStatus.model_validate(data))
