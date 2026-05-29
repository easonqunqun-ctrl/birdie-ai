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

import math
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
    InvitationRead,
    VenueCreate,
)
from app.services import meetup_feedback_service as feedback_svc

# Nearby 搜索硬上限：避免恶意客户端用极大 radius 把全国 venue 都拉下来。
MAX_NEARBY_RADIUS_KM: float = 100.0
# 默认返回数量；客户端可在 1-50 之间调整。
DEFAULT_NEARBY_LIMIT: int = 20
MAX_NEARBY_LIMIT: int = 50
# 地球半径（km）：haversine 公式标准取值
EARTH_RADIUS_KM: float = 6371.0088

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
        latitude=payload.latitude,
        longitude=payload.longitude,
        source=payload.source,
        contributor_user_id=contributor_user_id,
    )
    db.add(v)
    await db.flush()
    return v


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """两点间球面距离（km），haversine 公式.

    与 PostGIS ST_Distance 在小尺度（< 几百 km）误差 < 0.5%，对"找最近球场"
    完全足够。不引入 PostGIS 依赖，便于 SQLite 测试环境也跑通。
    """

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(
        dlam / 2
    ) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


async def search_nearby_venues(
    db: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    radius_km: float,
    limit: int = DEFAULT_NEARBY_LIMIT,
    venue_type: str | None = None,
) -> list[tuple[Venue, float]]:
    """搜索给定圆心 + 半径内的 active venues，按距离升序返回 (venue, distance_km).

    实现策略
    --------
    1. **粗筛**：经纬度 bounding box（lat ± Δ / lng ± Δ）走数据库 index
       减少候选集，避免全表 haversine
    2. **精筛**：Python haversine 计算精确距离，过滤 > radius 的伪命中
    3. **排序**：距离升序 + limit 截断

    参数校验
    --------
    - ``radius_km`` ∈ (0, MAX_NEARBY_RADIUS_KM]，否则 ``BadRequestError`` 40050
    - ``latitude`` ∈ [-90, 90], ``longitude`` ∈ [-180, 180]，否则 ``40050``
    - ``limit`` ∈ [1, MAX_NEARBY_LIMIT]

    错误码段位
    ----------
    40050-40059 归 M13 约球业务专用；本方法只用 40050。
    不复用 40015（已被 account_deletion / payment 占用）。
    """

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise BadRequestError(code=40050, message="latitude / longitude 超出范围")
    if not (0 < radius_km <= MAX_NEARBY_RADIUS_KM):
        raise BadRequestError(
            code=40050,
            message=f"radius_km 必须在 (0, {MAX_NEARBY_RADIUS_KM}] 之间",
        )
    limit = max(1, min(limit, MAX_NEARBY_LIMIT))

    # 经度的 1 度跨度 ≈ 111 km * cos(lat)；高纬度需要展开更大的 Δlng
    # 这里取保守 fallback：cos(lat) 接近 0 时直接走 ±180（赤道至极点边缘情况罕见）
    lat_delta = radius_km / 111.0
    cos_lat = math.cos(math.radians(latitude))
    lng_delta = 180.0 if cos_lat < 0.01 else radius_km / (111.0 * cos_lat)

    stmt = (
        select(Venue)
        .where(
            Venue.status == "active",
            Venue.latitude.isnot(None),
            Venue.longitude.isnot(None),
            Venue.latitude >= latitude - lat_delta,
            Venue.latitude <= latitude + lat_delta,
            Venue.longitude >= longitude - lng_delta,
            Venue.longitude <= longitude + lng_delta,
        )
    )
    if venue_type is not None:
        stmt = stmt.where(Venue.venue_type == venue_type)

    rows = await db.execute(stmt)
    candidates = list(rows.scalars().all())

    # 精筛 + 距离计算
    annotated: list[tuple[Venue, float]] = []
    for v in candidates:
        # 经过 NOT NULL 过滤后这两个不会为 None；但仍保险性 cast
        if v.latitude is None or v.longitude is None:
            continue
        d = haversine_km(latitude, longitude, float(v.latitude), float(v.longitude))
        if d <= radius_km:
            annotated.append((v, d))

    annotated.sort(key=lambda pair: pair[1])
    return annotated[:limit]


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
    # M13-04 通知钩子：accept 后通知 inviter（实际推送由 M13-04 push integration
    # 处理；此处只发结构化日志事件，留给后续 wechat_subscribe_message 模板就绪后
    # 接管）。不写 outbox 表是因为 outbox infra 还没就绪——先打日志事件，业务上线
    # 后改成 outbox 是非破坏性的。
    logger.info(
        "meetup.notification_due",
        kind="invitation_accepted",
        invitation_id=invitation_id,
        notify_user_id=inv.inviter_user_id,
        actor_user_id=user_id,
    )
    return inv


def filter_invitation_contact_for_user(
    inv: MeetupInvitation, *, viewer_user_id: str
) -> InvitationRead:
    """合规：``contact_payload`` 只对 inviter / invitee 可见，其他 viewer（含教练 /
    管理员视图）一律置 None。

    返回 Pydantic 投影，**不修改 ORM 实例**，避免 M13-10 教练旁观等场景在
    序列化后误 flush 把 ``contact_payload=None`` 持久化进 DB。
    """

    read = InvitationRead.model_validate(inv)
    if viewer_user_id not in {inv.inviter_user_id, inv.invitee_user_id}:
        return read.model_copy(update={"contact_payload": None})
    return read


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
    # 通知钩子（同 accept 走结构化日志事件）
    logger.info(
        "meetup.notification_due",
        kind="invitation_declined",
        invitation_id=invitation_id,
        notify_user_id=inv.inviter_user_id,
        actor_user_id=user_id,
    )
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


def calculate_credit_delta(rating: int, tags: list[str]) -> Decimal:
    return feedback_svc.calculate_feedback_credit_delta(rating=rating, tags=tags)


async def submit_feedback(
    db: AsyncSession, *, reviewer_user_id: str, payload: FeedbackCreate
) -> MeetupFeedback:
    from app.schemas.meetup import MeetupFeedbackSubmit

    return await feedback_svc.submit_feedback(
        db,
        reviewer_user_id=reviewer_user_id,
        payload=MeetupFeedbackSubmit(
            invitation_id=payload.invitation_id,
            rating=payload.rating,
            tags=list(payload.tags),
            comment=payload.comment,
        ),
    )


# ---------------- self-organized events ----------------


async def create_event(
    db: AsyncSession, *, organizer_user_id: str, payload: EventCreate
) -> SelfOrganizedEvent:
    from app.services import meetup_event_service as event_svc

    return await event_svc.create_event(
        db, organizer_user_id=organizer_user_id, payload=payload
    )


async def sign_up_event(
    db: AsyncSession, *, event_id: str, user_id: str
) -> EventParticipation:
    from app.services import meetup_event_service as event_svc

    return await event_svc.join_event(db, event_id=event_id, user_id=user_id)


__all__ = [
    "DEFAULT_NEARBY_LIMIT",
    "MAX_NEARBY_LIMIT",
    "MAX_NEARBY_RADIUS_KM",
    "accept_invitation",
    "calculate_credit_delta",
    "cancel_invitation",
    "create_event",
    "create_invitation",
    "create_venue",
    "decline_invitation",
    "expire_overdue_invitations",
    "filter_invitation_contact_for_user",
    "flag_venue",
    "haversine_km",
    "list_user_invitations",
    "search_nearby_venues",
    "sign_up_event",
    "submit_feedback",
]
