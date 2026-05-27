"""M13-01 meetup_service 单测（对齐 docs/23 §9.1 AC-3）.

合规守门是本任务的核心 AC：

- 反联系方式：手机号正则 / openid / unionid / wx_xxx 一律拒
- 自约球邀请不能给自己
- accept 只能接受发给自己的邀请
- 反馈只能由当事人提交
"""

from __future__ import annotations

from datetime import UTC, datetime

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
# M13-03 邀请列表 / 撤回 / 懒过期
# ============================================================================


@pytest.mark.asyncio
async def test_cancel_invitation_only_by_inviter_and_only_pending() -> None:
    """撤回守门：非 inviter 拒 / 非 pending 拒."""

    async with AsyncSessionLocal() as db:
        a = await _make_user(db)
        b = await _make_user(db)
        c = await _make_user(db)
        inv = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(invitee_user_id=b.id),
        )
        # 非 inviter 撤回 → 403
        with pytest.raises(ForbiddenError):
            await svc.cancel_invitation(db, invitation_id=inv.id, user_id=c.id)

        # accept 后再撤回 → 40903
        await svc.accept_invitation(db, invitation_id=inv.id, user_id=b.id)
        with pytest.raises(BadRequestError) as e:
            await svc.cancel_invitation(db, invitation_id=inv.id, user_id=a.id)
        assert e.value.code == 40903

        # 重新发一条 pending，inviter 撤回 → 成功
        inv2 = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(invitee_user_id=b.id),
        )
        cancelled = await svc.cancel_invitation(
            db, invitation_id=inv2.id, user_id=a.id
        )
        assert cancelled.status == "cancelled"


@pytest.mark.asyncio
async def test_list_user_invitations_role_and_status() -> None:
    """role / status 过滤组合."""

    async with AsyncSessionLocal() as db:
        a = await _make_user(db)
        b = await _make_user(db)
        c = await _make_user(db)
        # a 发给 b 和 c；c 发给 a
        inv_a_to_b = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(invitee_user_id=b.id),
        )
        inv_a_to_c = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(invitee_user_id=c.id),
        )
        inv_c_to_a = await svc.create_invitation(
            db,
            inviter_user_id=c.id,
            payload=InvitationCreate(invitee_user_id=a.id),
        )
        # a 接受 c 发来的
        await svc.accept_invitation(db, invitation_id=inv_c_to_a.id, user_id=a.id)

        # role=any：a 看到 3 条
        any_view = await svc.list_user_invitations(db, user_id=a.id, role="any")
        ids_any = {i.id for i in any_view}
        assert ids_any == {inv_a_to_b.id, inv_a_to_c.id, inv_c_to_a.id}

        # role=inviter：a 看到 2 条（a 发出的）
        inviter_view = await svc.list_user_invitations(
            db, user_id=a.id, role="inviter"
        )
        assert {i.id for i in inviter_view} == {inv_a_to_b.id, inv_a_to_c.id}

        # role=invitee + status=accepted：a 收到的已接受 = 1 条
        accepted = await svc.list_user_invitations(
            db, user_id=a.id, role="invitee", status="accepted"
        )
        assert len(accepted) == 1
        assert accepted[0].id == inv_c_to_a.id


@pytest.mark.asyncio
async def test_list_user_invitations_rejects_bad_params() -> None:
    """非法 role / status 抛 40051."""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        with pytest.raises(BadRequestError) as e1:
            await svc.list_user_invitations(db, user_id=u.id, role="bogus")
        assert e1.value.code == 40051

        with pytest.raises(BadRequestError) as e2:
            await svc.list_user_invitations(db, user_id=u.id, status="bogus")
        assert e2.value.code == 40051


@pytest.mark.asyncio
async def test_expire_overdue_invitations_only_pending_overdue() -> None:
    """expires_at < now 的 pending → expired；其他状态 / 未到期不动."""

    from datetime import timedelta

    async with AsyncSessionLocal() as db:
        a = await _make_user(db)
        b = await _make_user(db)
        # 过期的 pending
        overdue = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(
                invitee_user_id=b.id,
                expires_at=datetime.now(UTC) - timedelta(hours=1),
            ),
        )
        # 未到期的 pending
        future = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(
                invitee_user_id=b.id,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
        )
        # 已 accepted 的过期不应被动
        accepted_overdue = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(
                invitee_user_id=b.id,
                expires_at=datetime.now(UTC) - timedelta(hours=2),
            ),
        )
        await svc.accept_invitation(
            db, invitation_id=accepted_overdue.id, user_id=b.id
        )

        count = await svc.expire_overdue_invitations(db)
        assert count == 1

        await db.refresh(overdue)
        await db.refresh(future)
        await db.refresh(accepted_overdue)
        assert overdue.status == "expired"
        assert future.status == "pending"
        assert accepted_overdue.status == "accepted"


@pytest.mark.asyncio
async def test_expire_overdue_invitations_no_op_returns_zero() -> None:
    async with AsyncSessionLocal() as db:
        count = await svc.expire_overdue_invitations(db)
        assert count == 0
