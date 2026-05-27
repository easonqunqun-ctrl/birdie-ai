"""二期 M13 球友约球服务（对齐 docs/23 §9.1 / docs/06 §13.4）.

职责
----
- venues UGC + 运营 CRUD
- 邀请生命周期：``pending → accepted/declined/expired/cancelled``
- 反联系方式守门：accepted 后才允许写 contact_payload，且走 ``write_contact_payload``
- 反馈 / 信用分 ``credit_delta``（M13-07，本 PR 只写表 + 简单计算）
- 自组织事件 + 报名（M13-08 模板，本 PR 只建表 / CRUD）

刻意不做（M13-03~10 接力）
--------------------------
- 匹配 / 推荐算法（M13-04）
- 教练旁观视图（M13-10 service 已在 kickoff 详）
- UGC 内容审核接入（M8-08 / 微信内容安全）
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.meetup import (
    ContactPayloadComplianceError,
    EventParticipation,
    MeetupFeedback,
    MeetupInvitation,
    SelfOrganizedEvent,
    Venue,
    write_contact_payload,
)
from app.schemas.meetup import (
    EventCreate,
    FeedbackCreate,
    InvitationAcceptPayload,
    InvitationCreate,
    VenueCreate,
)

logger = get_logger("meetup")


# ---------------- venues ----------------


async def create_venue(
    db: AsyncSession,
    *,
    payload: VenueCreate,
    contributor_user_id: str | None,
) -> Venue:
    v = Venue(
        id=new_id("ven"),
        city=payload.city,
        name=payload.name,
        venue_type=payload.venue_type,
        address=payload.address,
        source=payload.source,
        contributor_user_id=contributor_user_id,
    )
    db.add(v)
    await db.flush()
    return v


async def flag_venue(db: AsyncSession, venue_id: str) -> Venue:
    v = await db.get(Venue, venue_id)
    if v is None:
        raise NotFoundError(code=40406, message="场地不存在")
    v.status = "flagged"
    await db.flush()
    return v


# ---------------- invitations ----------------


async def create_invitation(
    db: AsyncSession, *, inviter_user_id: str, payload: InvitationCreate
) -> MeetupInvitation:
    if inviter_user_id == payload.invitee_user_id:
        raise BadRequestError(code=40331, message="不能给自己发约球邀请")
    inv = MeetupInvitation(
        id=new_id("mvi"),
        inviter_user_id=inviter_user_id,
        invitee_user_id=payload.invitee_user_id,
        venue_id=payload.venue_id,
        proposed_time=payload.proposed_time,
        expires_at=payload.expires_at,
        status="pending",
    )
    db.add(inv)
    await db.flush()
    logger.info(
        "meetup_invitation_created",
        invitation_id=inv.id,
        inviter=inviter_user_id,
        invitee=payload.invitee_user_id,
    )
    return inv


async def accept_invitation(
    db: AsyncSession,
    *,
    invitation_id: str,
    user_id: str,
    contact_payload: InvitationAcceptPayload | None = None,
) -> MeetupInvitation:
    """被邀请人接受 → status='accepted' + 合规守门写 contact_payload."""

    inv = await db.get(MeetupInvitation, invitation_id)
    if inv is None:
        raise NotFoundError(code=40406, message="邀请不存在")
    if inv.invitee_user_id != user_id:
        raise ForbiddenError(code=40330, message="只能接受发给自己的邀请")
    if inv.status != "pending":
        raise BadRequestError(
            code=40903,
            message="邀请状态非 pending，不能接受",
            detail=inv.status,
        )

    inv.status = "accepted"
    inv.accepted_at = datetime.now(UTC)

    if contact_payload is not None:
        try:
            write_contact_payload(inv, contact_payload.model_dump(exclude_none=True))
        except ContactPayloadComplianceError as exc:
            raise BadRequestError(
                code=40335,
                message="contact_payload 含禁字段，请删除联系方式后重发",
                detail=str(exc),
            ) from exc

    await db.flush()
    logger.info("meetup_invitation_accepted", invitation_id=invitation_id, by=user_id)
    return inv


async def decline_invitation(
    db: AsyncSession, *, invitation_id: str, user_id: str
) -> MeetupInvitation:
    inv = await db.get(MeetupInvitation, invitation_id)
    if inv is None:
        raise NotFoundError(code=40406, message="邀请不存在")
    if inv.invitee_user_id != user_id:
        raise ForbiddenError(code=40330, message="只能拒绝发给自己的邀请")
    if inv.status != "pending":
        return inv
    inv.status = "declined"
    await db.flush()
    return inv


async def cancel_invitation(
    db: AsyncSession, *, invitation_id: str, user_id: str
) -> MeetupInvitation:
    """M13-03：邀请人主动撤回（pending 才允许；accepted 之后只能走 declined-by-invitee）."""

    inv = await db.get(MeetupInvitation, invitation_id)
    if inv is None:
        raise NotFoundError(code=40406, message="邀请不存在")
    if inv.inviter_user_id != user_id:
        raise ForbiddenError(code=40330, message="只能撤回自己发出的邀请")
    if inv.status != "pending":
        raise BadRequestError(
            code=40903,
            message="只有 pending 邀请可撤回",
            detail=inv.status,
        )
    inv.status = "cancelled"
    await db.flush()
    logger.info("meetup_invitation_cancelled", invitation_id=invitation_id)
    return inv


# M13-03 用户视角：作为 inviter / invitee / 双向（默认）查询自己的邀请列表
InvitationRoleLiteral = str  # "inviter" | "invitee" | "any"


async def list_user_invitations(
    db: AsyncSession,
    *,
    user_id: str,
    role: str = "any",
    status: str | None = None,
    limit: int = 50,
) -> list[MeetupInvitation]:
    """按角色 / 状态查询用户邀请，按 created_at 倒序.

    参数
    ----
    - ``role`` ∈ {``inviter``, ``invitee``, ``any``}；``any`` 等价于"两边都看"
    - ``status``：可选，``pending``/``accepted``/``declined``/``expired``/``cancelled``
    - ``limit``：上限 100，默认 50（前端列表分页可拉多次）
    """

    role = role or "any"
    if role not in {"inviter", "invitee", "any"}:
        # 40051 段：M13 约球业务码（40050-40059）；不复用 40016（注销/支付/训练已占）。
        raise BadRequestError(code=40051, message="role 必须是 inviter/invitee/any")
    limit = max(1, min(limit, 100))

    stmt = select(MeetupInvitation)
    if role == "inviter":
        stmt = stmt.where(MeetupInvitation.inviter_user_id == user_id)
    elif role == "invitee":
        stmt = stmt.where(MeetupInvitation.invitee_user_id == user_id)
    else:  # any
        stmt = stmt.where(
            (MeetupInvitation.inviter_user_id == user_id)
            | (MeetupInvitation.invitee_user_id == user_id)
        )
    if status is not None:
        # 不在合法状态集合 → 直接 40051（避免 SQLAlchemy 抛 OperationalError）
        if status not in {"pending", "accepted", "declined", "expired", "cancelled"}:
            raise BadRequestError(code=40051, message=f"status 非法: {status}")
        stmt = stmt.where(MeetupInvitation.status == status)

    stmt = stmt.order_by(MeetupInvitation.created_at.desc()).limit(limit)
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def expire_overdue_invitations(db: AsyncSession) -> int:
    """把 ``expires_at < now`` 的 pending 邀请置为 expired，返回处理条数.

    设计要点
    --------
    - 仅处理 ``pending``：accepted / declined / cancelled 不动
    - 不靠 cron；本 PR 由 list_user_invitations / accept_invitation 顺手调用，
      让 GET / POST 自带"懒清理"。这样真机不依赖 background job 也能体验正确状态
    - 返回处理条数便于 logging
    """

    now = datetime.now(UTC)
    rows = await db.execute(
        select(MeetupInvitation).where(
            MeetupInvitation.status == "pending",
            MeetupInvitation.expires_at.is_not(None),
            MeetupInvitation.expires_at < now,
        )
    )
    overdue = list(rows.scalars().all())
    if not overdue:
        return 0
    for inv in overdue:
        inv.status = "expired"
    await db.flush()
    logger.info("meetup_invitations_expired", count=len(overdue))
    return len(overdue)


# ---------------- feedback / credit ----------------


_RATING_TO_CREDIT_DELTA: dict[int, Decimal] = {
    1: Decimal("-5"),
    2: Decimal("-2"),
    3: Decimal("0"),
    4: Decimal("2"),
    5: Decimal("5"),
}


def calculate_credit_delta(rating: int, tags: list[str]) -> Decimal:
    """简单算法：rating 基线 + 每个负向 tag -1（capped -10..+10）."""

    base = _RATING_TO_CREDIT_DELTA.get(rating, Decimal("0"))
    negative = {"no_show", "rude", "late", "danger"}
    penalty = Decimal("-1") * sum(1 for t in tags if t in negative)
    delta = base + penalty
    if delta < Decimal("-10"):
        delta = Decimal("-10")
    if delta > Decimal("10"):
        delta = Decimal("10")
    return delta


async def submit_feedback(
    db: AsyncSession, *, reviewer_user_id: str, payload: FeedbackCreate
) -> MeetupFeedback:
    if reviewer_user_id == payload.reviewee_user_id:
        raise BadRequestError(code=40331, message="不能给自己写反馈")
    inv = await db.get(MeetupInvitation, payload.invitation_id)
    if inv is None:
        raise NotFoundError(code=40406, message="邀请不存在")
    if inv.status != "accepted":
        raise BadRequestError(
            code=40903,
            message="只能对 accepted 的邀请提交反馈",
            detail=inv.status,
        )
    if reviewer_user_id not in {inv.inviter_user_id, inv.invitee_user_id}:
        raise ForbiddenError(code=40330, message="非约球当事人无法反馈")

    delta = calculate_credit_delta(payload.rating, payload.tags)
    fb = MeetupFeedback(
        id=new_id("mfb"),
        invitation_id=payload.invitation_id,
        reviewer_user_id=reviewer_user_id,
        reviewee_user_id=payload.reviewee_user_id,
        rating=payload.rating,
        tags=list(payload.tags),
        credit_delta=delta,
        comment=payload.comment,
    )
    db.add(fb)
    await db.flush()
    logger.info(
        "meetup_feedback_submitted",
        feedback_id=fb.id,
        reviewer=reviewer_user_id,
        reviewee=payload.reviewee_user_id,
        rating=payload.rating,
        credit_delta=str(delta),
    )
    return fb


# ---------------- self-organized events ----------------


async def create_event(
    db: AsyncSession, *, organizer_user_id: str, payload: EventCreate
) -> SelfOrganizedEvent:
    e = SelfOrganizedEvent(
        id=new_id("soe"),
        organizer_user_id=organizer_user_id,
        venue_id=payload.venue_id,
        title=payload.title,
        description=payload.description,
        template_code=payload.template_code,
        scheduled_at=payload.scheduled_at,
        capacity=payload.capacity,
        badge_template_code=payload.badge_template_code,
        rules_payload=dict(payload.rules_payload or {}),
    )
    db.add(e)
    await db.flush()
    logger.info(
        "event_created",
        event_id=e.id,
        organizer=organizer_user_id,
        template=payload.template_code,
    )
    return e


async def sign_up_event(
    db: AsyncSession, *, event_id: str, user_id: str
) -> EventParticipation:
    e = await db.get(SelfOrganizedEvent, event_id)
    if e is None:
        raise NotFoundError(code=40406, message="活动不存在")
    if e.status not in {"open"}:
        raise BadRequestError(code=40903, message="活动未开放报名", detail=e.status)

    # 容量校验（粗略）
    if e.capacity is not None:
        cnt_q = await db.execute(
            select(EventParticipation).where(
                EventParticipation.event_id == event_id,
                EventParticipation.status.in_(["signed_up", "checked_in", "completed"]),
            )
        )
        if len(list(cnt_q.scalars().all())) >= e.capacity:
            raise BadRequestError(code=40903, message="活动已报满")

    p = EventParticipation(
        id=new_id("evp"),
        event_id=event_id,
        user_id=user_id,
        status="signed_up",
    )
    db.add(p)
    await db.flush()
    return p


__all__ = [
    "accept_invitation",
    "calculate_credit_delta",
    "cancel_invitation",
    "create_event",
    "create_invitation",
    "create_venue",
    "decline_invitation",
    "expire_overdue_invitations",
    "flag_venue",
    "list_user_invitations",
    "sign_up_event",
    "submit_feedback",
]
