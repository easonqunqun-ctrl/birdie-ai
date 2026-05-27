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
# M13-04 contact_payload 可见性 + 通知钩子
# ============================================================================


@pytest.mark.asyncio
async def test_filter_contact_payload_visibility() -> None:
    """contact_payload 对当事人可见、对第三方不可见."""

    async with AsyncSessionLocal() as db:
        a = await _make_user(db)
        b = await _make_user(db)
        c = await _make_user(db)
        inv = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(invitee_user_id=b.id),
        )
        await svc.accept_invitation(
            db,
            invitation_id=inv.id,
            user_id=b.id,
            contact_payload=InvitationAcceptPayload(note="见面在 7 号洞"),
        )
        await db.refresh(inv)
        assert inv.contact_payload is not None
        original_note = inv.contact_payload.get("note")

        # 第三方 viewer → contact_payload 被置 None
        masked = svc.filter_invitation_contact_for_user(inv, viewer_user_id=c.id)
        assert masked.contact_payload is None
        # ORM 未被 in-place 污染；当事人仍可读到原始 contact_payload
        assert inv.contact_payload is not None
        assert inv.contact_payload.get("note") == original_note

        kept = svc.filter_invitation_contact_for_user(inv, viewer_user_id=a.id)
        assert kept.contact_payload is not None
        assert kept.contact_payload.get("note") == original_note


@pytest.mark.asyncio
async def test_accept_emits_notification_due_log(caplog) -> None:
    """accept 后 service 必须发结构化日志事件 meetup.notification_due."""

    import logging

    caplog.set_level(logging.INFO)
    async with AsyncSessionLocal() as db:
        a = await _make_user(db)
        b = await _make_user(db)
        inv = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(invitee_user_id=b.id),
        )
        await svc.accept_invitation(
            db, invitation_id=inv.id, user_id=b.id
        )

    found = [
        r for r in caplog.records
        if "meetup.notification_due" in r.getMessage()
        or "notification_due" in (getattr(r, "msg", "") or "")
    ]
    assert found, "expected meetup.notification_due structured log on accept"


@pytest.mark.asyncio
async def test_decline_emits_notification_due_log(caplog) -> None:
    """decline 同样发通知事件."""

    import logging

    caplog.set_level(logging.INFO)
    async with AsyncSessionLocal() as db:
        a = await _make_user(db)
        b = await _make_user(db)
        inv = await svc.create_invitation(
            db,
            inviter_user_id=a.id,
            payload=InvitationCreate(invitee_user_id=b.id),
        )
        await svc.decline_invitation(
            db, invitation_id=inv.id, user_id=b.id
        )

    found = [
        r for r in caplog.records
        if "meetup.notification_due" in r.getMessage()
        or "notification_due" in (getattr(r, "msg", "") or "")
    ]
    assert found
