"""M13-10 · 教练旁观学员约球（去识别对方 + 隐私 opt-in 守门）."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import CoachSpectatorNotAllowedError, NotFoundError
from app.core.logging import get_logger
from app.models.user import User
from app.models.user_profile_v2 import UserProfileV2
from app.schemas.coach_spectator import (
    CoachSpectatorInvitationRead,
    CoachStudentMeetupsResponse,
)
from app.services import meetup_safety_service as safety_svc
from app.services import meetup_service
from app.services.coach_student_service import require_active_relation

logger = get_logger("coach_spectator")

COACH_SPECTATOR_OPTIN_KEY = "coach_spectator_optin"
REDACTED_PEER_USER_ID = "usr_redacted"


def ensure_coach_spectator_enabled() -> None:
    if not settings.PHASE2_MEETUP_ENABLED:
        raise NotFoundError(code=40406, message="约球功能未开放")


def _assert_student_spectator_consent(payload: dict) -> None:
    if not payload.get(safety_svc.MEETUP_TOS_KEY):
        raise CoachSpectatorNotAllowedError()
    if not payload.get(COACH_SPECTATOR_OPTIN_KEY):
        raise CoachSpectatorNotAllowedError()


def _to_spectator_read(
    inv,
    *,
    student_id: str,
    coach_user_id: str,
) -> CoachSpectatorInvitationRead:
    """投影邀请：对方 user_id 去识别；contact_payload 永不返回."""

    if inv.inviter_user_id == student_id:
        student_role = "inviter"
    elif inv.invitee_user_id == student_id:
        student_role = "invitee"
    else:
        # 不应出现：list 已按 student_id 过滤
        student_role = "inviter"

    meetup_service.filter_invitation_contact_for_user(
        inv, viewer_user_id=coach_user_id
    )
    return CoachSpectatorInvitationRead(
        id=inv.id,
        student_role=student_role,  # type: ignore[arg-type]
        peer_user_id=REDACTED_PEER_USER_ID,
        peer_redacted=True,
        venue_id=inv.venue_id,
        proposed_time=inv.proposed_time,
        expires_at=inv.expires_at,
        status=inv.status,  # type: ignore[arg-type]
        accepted_at=inv.accepted_at,
        created_at=inv.created_at,
    )


async def list_student_meetups_for_coach(
    db: AsyncSession,
    *,
    coach: User,
    student_id: str,
    page: int = 1,
    page_size: int = 20,
) -> CoachStudentMeetupsResponse:
    ensure_coach_spectator_enabled()
    await require_active_relation(db, coach=coach, student_id=student_id)

    profile = await db.get(UserProfileV2, student_id)
    payload = dict((profile.privacy_payload if profile else None) or {})
    _assert_student_spectator_consent(payload)

    page = max(1, page)
    page_size = max(1, min(page_size, 50))
    limit = page * page_size

    await meetup_service.expire_overdue_invitations(db)
    invitations = await meetup_service.list_user_invitations(
        db, user_id=student_id, role="any", limit=limit
    )
    start = (page - 1) * page_size
    page_items = invitations[start : start + page_size]
    items = [
        _to_spectator_read(inv, student_id=student_id, coach_user_id=coach.id)
        for inv in page_items
    ]
    total = len(invitations)

    logger.info(
        "coach_spectator_list",
        coach_user_id=coach.id,
        student_user_id=student_id,
        total=total,
    )
    return CoachStudentMeetupsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        student_user_id=student_id,
    )


async def get_coach_spectator_optin(db: AsyncSession, *, user: User) -> bool:
    profile = await db.get(UserProfileV2, user.id)
    payload = dict((profile.privacy_payload if profile else None) or {})
    return bool(payload.get(COACH_SPECTATOR_OPTIN_KEY))


async def update_coach_spectator_optin(
    db: AsyncSession, *, user: User, optin: bool
) -> bool:
    """学员侧开关：须已满足 M13 合规."""

    await safety_svc.update_coach_spectator_optin(db, user=user, optin=optin)
    return optin


__all__ = [
    "COACH_SPECTATOR_OPTIN_KEY",
    "REDACTED_PEER_USER_ID",
    "ensure_coach_spectator_enabled",
    "get_coach_spectator_optin",
    "list_student_meetups_for_coach",
    "update_coach_spectator_optin",
]
