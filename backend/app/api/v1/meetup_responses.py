"""二期 M13 约球邀请响应端点（M13-04）.

本 PR 提供
----------
- ``POST /v1/meetups/invitations/{id}/accept`` — 被邀请人接受 + 合规守门 contact_payload
- ``POST /v1/meetups/invitations/{id}/decline`` — 被邀请人拒绝

通知钩子
--------
service 层在 accept / decline 之后会发结构化日志事件 ``meetup.notification_due``，
后续 M13-04 push integration（wechat_subscribe_message 模板）接管做实际下发。
本 PR 不引入推送依赖，保持守门 / 状态机 / 合规这三件事原子化。

合规：``contact_payload`` 仅对当事人可见
---------------------------------------
service.``filter_invitation_contact_for_user`` 是合规过滤器；任何返回 invitation
给 viewer 时调用一次，非当事人会拿到 ``contact_payload=None``。

灰度
----
``PHASE2_MEETUP_ENABLED=False`` → 全部端点 404。
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.meetup import InvitationAcceptPayload, InvitationRead
from app.services import meetup_risk_service as risk_svc
from app.services import meetup_service

router = APIRouter()


def _ensure_meetup_enabled() -> None:
    if not settings.PHASE2_MEETUP_ENABLED:
        raise NotFoundError(code=40406, message="约球功能未开放")


# ==================== POST /v1/meetups/invitations/{id}/accept ====================
@router.post(
    "/invitations/{invitation_id}/accept",
    summary="被邀请人接受约球邀请（M13-04）",
    response_model=APIResponse[InvitationRead],
)
async def accept_meetup_invitation(
    invitation_id: str,
    contact_payload: InvitationAcceptPayload | None = Body(
        None,
        description=(
            "可选 contact_payload；服务器会拒掉手机 / openid / unionid / "
            "wx_xxx 等敏感字段（合规守门），违规返 40335。"
        ),
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """守门链：非 invitee → 40330；非 pending → 40903；contact 含禁字段 → 40335.

    成功时 service 顺手发结构化日志事件 ``meetup.notification_due``；
    后续推送由 M13-04 完成。
    """

    _ensure_meetup_enabled()
    inv = await meetup_service.accept_invitation(
        db,
        invitation_id=invitation_id,
        user_id=user.id,
        contact_payload=contact_payload,
    )
    await risk_svc.on_invitation_accepted(redis, inviter_user_id=inv.inviter_user_id)
    await db.commit()
    inv = meetup_service.filter_invitation_contact_for_user(
        inv, viewer_user_id=user.id
    )
    return ok(inv)


# ==================== POST /v1/meetups/invitations/{id}/decline ====================
@router.post(
    "/invitations/{invitation_id}/decline",
    summary="被邀请人拒绝约球邀请（M13-04）",
    response_model=APIResponse[InvitationRead],
)
async def decline_meetup_invitation(
    invitation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """非 invitee → 40330；非 pending → 幂等返回当前状态."""

    _ensure_meetup_enabled()
    inv = await meetup_service.decline_invitation(
        db, invitation_id=invitation_id, user_id=user.id
    )
    if inv.status == "declined":
        cfg = await risk_svc.get_risk_config(redis)
        await risk_svc.on_invitation_declined(
            redis, inviter_user_id=inv.inviter_user_id, config=cfg
        )
    await db.commit()
    inv = meetup_service.filter_invitation_contact_for_user(
        inv, viewer_user_id=user.id
    )
    return ok(inv)
