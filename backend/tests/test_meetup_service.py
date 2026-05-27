"""M13-01 meetup_service 单测（对齐 docs/23 §9.1 AC-3）.

合规守门是本任务的核心 AC：

- 反联系方式：手机号正则 / openid / unionid / wx_xxx 一律拒
- 自约球邀请不能给自己
- accept 只能接受发给自己的邀请
- 反馈只能由当事人提交
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError, ForbiddenError
from app.core.security import new_id
from app.models.meetup import (
    ContactPayloadComplianceError,
    MeetupInvitation,
    write_contact_payload,
)
from app.models.user import User
from app.schemas.meetup import (
    EventCreate,
    FeedbackCreate,
    InvitationAcceptPayload,
    InvitationCreate,
    VenueCreate,
)
from app.services import meetup_service as svc


async def _make_user(db: AsyncSession) -> User:
    u = User(
        id=new_id("usr"),
        wechat_openid=f"o_{new_id('mock')}",
        nickname="t",
        invite_code=new_id("inv")[-6:].upper(),
    )
    db.add(u)
    await db.flush()
    return u


# ============================================================================
# 反联系方式（纯函数，无需 DB）
# ============================================================================


def test_write_contact_payload_rejects_phone_number() -> None:
    inv = MeetupInvitation(
        id="mvi_test",
        inviter_user_id="usr_a",
        invitee_user_id="usr_b",
        status="accepted",
    )
    with pytest.raises(ContactPayloadComplianceError):
        write_contact_payload(inv, {"note": "电话 13912345678 联系我"})


def test_write_contact_payload_rejects_openid_key() -> None:
    inv = MeetupInvitation(
        id="mvi_test",
        inviter_user_id="usr_a",
        invitee_user_id="usr_b",
        status="accepted",
    )
    with pytest.raises(ContactPayloadComplianceError):
        write_contact_payload(inv, {"openid": "o123"})


def test_write_contact_payload_rejects_wx_id() -> None:
    inv = MeetupInvitation(
        id="mvi_test",
        inviter_user_id="usr_a",
        invitee_user_id="usr_b",
        status="accepted",
    )
    with pytest.raises(ContactPayloadComplianceError):
        write_contact_payload(inv, {"note": "微信 wx_alice_2025 找我"})


def test_write_contact_payload_accepts_clean_note() -> None:
    inv = MeetupInvitation(
        id="mvi_test",
        inviter_user_id="usr_a",
        invitee_user_id="usr_b",
        status="accepted",
    )
    write_contact_payload(inv, {"note": "今晚 7 点海门一号场地见", "meet_at": "门口"})
    assert inv.contact_payload["note"].startswith("今晚")


# ============================================================================
# 邀请生命周期
# ============================================================================


@pytest.mark.asyncio
async def test_create_invitation_rejects_self() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        with pytest.raises(BadRequestError):
            await svc.create_invitation(
                db,
                inviter_user_id=u.id,
                payload=InvitationCreate(invitee_user_id=u.id),
            )


@pytest.mark.asyncio
async def test_accept_invitation_only_invitee() -> None:
    async with AsyncSessionLocal() as db:
        a = await _make_user(db)
        b = await _make_user(db)
        c = await _make_user(db)
        inv = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(invitee_user_id=b.id),
        )
        with pytest.raises(ForbiddenError):
            await svc.accept_invitation(db, invitation_id=inv.id, user_id=c.id)

        accepted = await svc.accept_invitation(
            db,
            invitation_id=inv.id,
            user_id=b.id,
            contact_payload=InvitationAcceptPayload(note="见", meet_at="门口"),
        )
        assert accepted.status == "accepted"
        assert accepted.accepted_at is not None


@pytest.mark.asyncio
async def test_accept_invitation_rejects_leaky_contact() -> None:
    async with AsyncSessionLocal() as db:
        a = await _make_user(db)
        b = await _make_user(db)
        inv = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(invitee_user_id=b.id),
        )
        with pytest.raises(BadRequestError):
            await svc.accept_invitation(
                db,
                invitation_id=inv.id,
                user_id=b.id,
                contact_payload=InvitationAcceptPayload(note="13912345678"),
            )


# ============================================================================
# venues
# ============================================================================


@pytest.mark.asyncio
async def test_create_venue_ugc() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        v = await svc.create_venue(
            db,
            payload=VenueCreate(
                city="上海",
                name="海门一号室内打位",
                venue_type="indoor_range",
            ),
            contributor_user_id=u.id,
        )
        assert v.source == "ugc"
        assert v.status == "active"


# ============================================================================
# 反馈 / 信用分
# ============================================================================


@pytest.mark.asyncio
async def test_feedback_credit_delta_computation() -> None:
    delta_good = svc.calculate_credit_delta(5, [])
    delta_bad = svc.calculate_credit_delta(1, ["no_show", "rude"])
    assert delta_good > 0
    assert delta_bad <= -5  # capped 但应该明显为负


@pytest.mark.asyncio
async def test_feedback_only_for_accepted_invitations() -> None:
    async with AsyncSessionLocal() as db:
        a = await _make_user(db)
        b = await _make_user(db)
        inv = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(invitee_user_id=b.id),
        )
        # 未 accept 状态 → 反馈被拒
        with pytest.raises(BadRequestError):
            await svc.submit_feedback(
                db,
                reviewer_user_id=a.id,
                payload=FeedbackCreate(
                    invitation_id=inv.id,
                    reviewee_user_id=b.id,
                    rating=4,
                ),
            )
        # accept 后可以反馈
        await svc.accept_invitation(db, invitation_id=inv.id, user_id=b.id)
        fb = await svc.submit_feedback(
            db,
            reviewer_user_id=a.id,
            payload=FeedbackCreate(
                invitation_id=inv.id,
                reviewee_user_id=b.id,
                rating=4,
                tags=["punctual"],
            ),
        )
        assert fb.rating == 4
        assert fb.credit_delta > 0


@pytest.mark.asyncio
async def test_feedback_only_by_participants() -> None:
    async with AsyncSessionLocal() as db:
        a = await _make_user(db)
        b = await _make_user(db)
        c = await _make_user(db)
        inv = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(invitee_user_id=b.id),
        )
        await svc.accept_invitation(db, invitation_id=inv.id, user_id=b.id)
        with pytest.raises(ForbiddenError):
            await svc.submit_feedback(
                db,
                reviewer_user_id=c.id,
                payload=FeedbackCreate(
                    invitation_id=inv.id,
                    reviewee_user_id=b.id,
                    rating=5,
                ),
            )


# ============================================================================
# 自组织事件
# ============================================================================


@pytest.mark.asyncio
async def test_create_event_no_cash_reward_field() -> None:
    """schema 层禁止 reward_cash / reward_item 字段（extra='forbid'）."""

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        EventCreate(title="不允许的现金挑战", reward_cash=100)  # type: ignore[call-arg]


# ============================================================================
# M13-02 nearby haversine 搜索
# ============================================================================


def test_haversine_known_distances() -> None:
    """Beijing ↔ Shanghai 约 1067km；同点 = 0；纬度 1° ≈ 111km."""

    bj = (39.9042, 116.4074)
    sh = (31.2304, 121.4737)
    d = svc.haversine_km(bj[0], bj[1], sh[0], sh[1])
    assert 1060 < d < 1080, f"Beijing↔Shanghai got {d}"
    # 同点
    assert svc.haversine_km(bj[0], bj[1], bj[0], bj[1]) < 1e-6
    # 纬度 1° ≈ 111km
    d_lat = svc.haversine_km(0, 0, 1, 0)
    assert 110 < d_lat < 112


@pytest.mark.asyncio
async def test_search_nearby_filters_by_radius() -> None:
    """5km 半径内只返圆心周边场地，excludes 距离更远的."""

    center_lat, center_lng = 39.9042, 116.4074  # 天安门

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        # 同点（0km）
        near = await svc.create_venue(
            db,
            payload=VenueCreate(
                city="北京",
                name="附近场",
                venue_type="indoor_range",
                latitude=39.9042,
                longitude=116.4074,
            ),
            contributor_user_id=u.id,
        )
        # ≈ 2km
        mid = await svc.create_venue(
            db,
            payload=VenueCreate(
                city="北京",
                name="中等距离",
                venue_type="indoor_range",
                latitude=39.92,
                longitude=116.41,
            ),
            contributor_user_id=u.id,
        )
        # ≈ 50km
        far = await svc.create_venue(
            db,
            payload=VenueCreate(
                city="北京",
                name="远场",
                venue_type="indoor_range",
                latitude=40.3,
                longitude=116.7,
            ),
            contributor_user_id=u.id,
        )
        # 无坐标 → nearby 不可见
        no_geo = await svc.create_venue(
            db,
            payload=VenueCreate(
                city="北京", name="无坐标", venue_type="indoor_range"
            ),
            contributor_user_id=u.id,
        )

        await db.flush()
        results = await svc.search_nearby_venues(
            db,
            latitude=center_lat,
            longitude=center_lng,
            radius_km=5.0,
        )
        ids = [v.id for v, _ in results]
        assert near.id in ids
        assert mid.id in ids
        assert far.id not in ids
        assert no_geo.id not in ids
        # 第一个一定是同点（距离最小）
        assert results[0][0].id == near.id
        # 距离单调递增
        distances = [d for _, d in results]
        assert distances == sorted(distances)


@pytest.mark.asyncio
async def test_search_nearby_venue_type_filter() -> None:
    """venue_type 过滤生效."""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        await svc.create_venue(
            db,
            payload=VenueCreate(
                city="北京",
                name="室内场 A",
                venue_type="indoor_range",
                latitude=39.9,
                longitude=116.4,
            ),
            contributor_user_id=u.id,
        )
        await svc.create_venue(
            db,
            payload=VenueCreate(
                city="北京",
                name="模拟器 A",
                venue_type="simulator_lounge",
                latitude=39.9,
                longitude=116.4,
            ),
            contributor_user_id=u.id,
        )
        await db.flush()

        only_indoor = await svc.search_nearby_venues(
            db,
            latitude=39.9,
            longitude=116.4,
            radius_km=10.0,
            venue_type="indoor_range",
        )
        types = {v.venue_type for v, _ in only_indoor}
        assert types == {"indoor_range"}


@pytest.mark.asyncio
async def test_search_nearby_rejects_invalid_params() -> None:
    """非法 lat/lng/radius 抛 40050。

    40050 段位归 M13 约球业务；不复用 40015（已被 account_deletion / payment / training 占）。
    """

    async with AsyncSessionLocal() as db:
        # 超出范围
        with pytest.raises(BadRequestError) as e1:
            await svc.search_nearby_venues(
                db, latitude=200, longitude=0, radius_km=5.0
            )
        assert e1.value.code == 40050

        # radius 超上限
        with pytest.raises(BadRequestError) as e2:
            await svc.search_nearby_venues(
                db, latitude=0, longitude=0, radius_km=svc.MAX_NEARBY_RADIUS_KM + 1
            )
        assert e2.value.code == 40050

        # radius <= 0
        with pytest.raises(BadRequestError) as e3:
            await svc.search_nearby_venues(
                db, latitude=0, longitude=0, radius_km=0
            )
        assert e3.value.code == 40050


@pytest.mark.asyncio
async def test_search_nearby_excludes_inactive_status() -> None:
    """flagged / closed venue 不出现在 nearby 结果."""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        active = await svc.create_venue(
            db,
            payload=VenueCreate(
                city="北京",
                name="active",
                venue_type="indoor_range",
                latitude=39.9,
                longitude=116.4,
            ),
            contributor_user_id=u.id,
        )
        flagged = await svc.create_venue(
            db,
            payload=VenueCreate(
                city="北京",
                name="flagged",
                venue_type="indoor_range",
                latitude=39.9,
                longitude=116.4,
            ),
            contributor_user_id=u.id,
        )
        await svc.flag_venue(db, flagged.id)
        await db.flush()

        results = await svc.search_nearby_venues(
            db, latitude=39.9, longitude=116.4, radius_km=5.0
        )
        ids = {v.id for v, _ in results}
        assert active.id in ids
        assert flagged.id not in ids
