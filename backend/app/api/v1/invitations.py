"""邀请相关 API（W7-T4）.

端点：
- `GET /v1/users/me/invitations`  我发出的邀请记录（invitee 昵称脱敏）
- `GET /v1/users/me/invite-info`  我的邀请概览（邀请码 + valid 数 + 距下档奖励）
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.invitation import InvitationItem, InviteInfo
from app.services import invitation_service

me_router = APIRouter()


@me_router.get(
    "/invitations",
    summary="我发出的邀请记录",
    response_model=APIResponse[list[InvitationItem]],
)
async def list_my_invitations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[InvitationItem]]:
    rows = await invitation_service.list_my_invitations(db, user)
    items = [
        InvitationItem(
            id=inv.id,
            invitee_id=inv.invitee_id,
            invitee_nickname_masked=invitation_service.mask_nickname(u.nickname),
            status=inv.status,  # type: ignore[arg-type]
            bonus_granted=inv.bonus_granted,
            bonus_granted_at=inv.bonus_granted_at,
            created_at=inv.created_at,
        )
        for inv, u in rows
    ]
    return ok(items)


@me_router.get(
    "/invite-info",
    summary="我的邀请概览（邀请码 + 进度条数据）",
    response_model=APIResponse[InviteInfo],
)
async def get_invite_info(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[InviteInfo]:
    overview = await invitation_service.get_invite_overview(db, user)
    return ok(InviteInfo(**overview))
