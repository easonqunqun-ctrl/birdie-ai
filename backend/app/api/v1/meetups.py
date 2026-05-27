"""二期 M13 约球邀请端点（对齐 docs/23 §9.1 · M13-03）.

本 PR 提供
----------
- ``POST /v1/meetups/invitations`` — 创建邀请（仅当前登录用户为 inviter）
- ``POST /v1/meetups/invitations/{id}/cancel`` — 邀请人撤回 pending 邀请
- ``GET  /v1/users/me/meetup-invitations?role=&status=&limit=`` — 我的邀请列表

后续 PR
-------
- M13-04 accept / decline + 推送（service 已就绪，等待 wechat push 模板）
- contact_payload 的"仅当事人可见"细节由 M13-04 引入

灰度
----
``PHASE2_MEETUP_ENABLED=False`` → 全部端点 404，与 M13-02 venues 守门同模式。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.meetup import (
    InvitationCreate,
    InvitationListResponse,
    InvitationRead,
    InvitationStatusLiteral,
)
from app.services import meetup_service

router = APIRouter()
me_router = APIRouter()


def _ensure_meetup_enabled() -> None:
    if not settings.PHASE2_MEETUP_ENABLED:
        raise NotFoundError(code=40406, message="约球功能未开放")


# ==================== POST /v1/meetups/invitations ====================
@router.post(
    "/invitations",
    summary="创建约球邀请（M13-03）",
    response_model=APIResponse[InvitationRead],
)
async def create_meetup_invitation(
    payload: InvitationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """当前登录用户作为 inviter，发起约球邀请.

    服务层守门：``invitee_user_id == inviter_user_id`` → 40331（不能给自己发）。
    """

    _ensure_meetup_enabled()
    inv = await meetup_service.create_invitation(
        db, inviter_user_id=user.id, payload=payload
    )
    await db.commit()
    return ok(InvitationRead.model_validate(inv))


# ==================== POST /v1/meetups/invitations/{id}/cancel ====================
@router.post(
    "/invitations/{invitation_id}/cancel",
    summary="邀请人撤回 pending 邀请（M13-03）",
    response_model=APIResponse[InvitationRead],
)
async def cancel_meetup_invitation(
    invitation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_meetup_enabled()
    inv = await meetup_service.cancel_invitation(
        db, invitation_id=invitation_id, user_id=user.id
    )
    await db.commit()
    return ok(InvitationRead.model_validate(inv))


# ==================== GET /v1/users/me/meetup-invitations ====================
@me_router.get(
    "/meetup-invitations",
    summary="我的约球邀请列表（M13-03）",
    response_model=APIResponse[InvitationListResponse],
)
async def list_my_meetup_invitations(
    role: str = Query(
        "any",
        description="inviter / invitee / any（默认 any 等价于「两边都看」）",
    ),
    status: InvitationStatusLiteral | None = Query(
        None, description="可选状态过滤"
    ),
    limit: int = Query(50, ge=1, le=100, description="返回上限"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按 role + status 过滤，按 ``created_at`` 倒序返回当前用户的邀请.

    顺手做一次 ``expire_overdue_invitations``：让用户每次刷新列表就能看到
    已经过期的邀请变为 ``expired``，不依赖 cron job。
    """

    _ensure_meetup_enabled()
    # 懒清理过期邀请（每次拉列表都顺手做一遍；O(过期数)，对中小流量足够）
    await meetup_service.expire_overdue_invitations(db)

    invitations = await meetup_service.list_user_invitations(
        db, user_id=user.id, role=role, status=status, limit=limit
    )
    items = [InvitationRead.model_validate(i) for i in invitations]
    await db.commit()
    return ok(
        InvitationListResponse(
            items=items,
            total=len(items),
            role=role,
            status=status,
        )
    )
