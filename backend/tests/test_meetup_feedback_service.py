"""M13-07 · meetup_feedback_service 单测."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import ConflictError
from app.core.security import new_id
from app.models.user import User
from app.schemas.meetup import InvitationCreate, MeetupFeedbackSubmit
from app.services import meetup_feedback_service as fb_svc
from app.services import meetup_service as meetup_svc


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


async def _accepted_invitation(db: AsyncSession):
    a = await _make_user(db)
    b = await _make_user(db)
    inv = await meetup_svc.create_invitation(
        db,
        inviter_user_id=a.id,
        payload=InvitationCreate(invitee_user_id=b.id),
    )
    inv = await meetup_svc.accept_invitation(
        db, invitation_id=inv.id, user_id=b.id
    )
    inv.accepted_at = datetime.now(UTC) - timedelta(hours=25)
    await db.flush()
    return a, b, inv


@pytest.mark.asyncio
async def test_duplicate_feedback_rejected() -> None:
    async with AsyncSessionLocal() as db:
        a, b, inv = await _accepted_invitation(db)
        payload = MeetupFeedbackSubmit(
            invitation_id=inv.id, rating=5, tags=["on_time"]
        )
        await fb_svc.submit_feedback(db, reviewer_user_id=a.id, payload=payload)
        with pytest.raises(ConflictError):
            await fb_svc.submit_feedback(db, reviewer_user_id=a.id, payload=payload)


@pytest.mark.asyncio
async def test_peer_feedback_hidden_until_24h_after_mine() -> None:
    async with AsyncSessionLocal() as db:
        a, b, inv = await _accepted_invitation(db)
        await fb_svc.submit_feedback(
            db,
            reviewer_user_id=a.id,
            payload=MeetupFeedbackSubmit(
                invitation_id=inv.id, rating=4, tags=["friendly"]
            ),
        )
        await fb_svc.submit_feedback(
            db,
            reviewer_user_id=b.id,
            payload=MeetupFeedbackSubmit(
                invitation_id=inv.id, rating=5, tags=["on_time"]
            ),
        )
        items = await fb_svc.list_feedbacks_for_invitation(
            db, viewer_user_id=a.id, invitation_id=inv.id
        )
        assert len(items) == 1

        mine = items[0]
        mine.created_at = datetime.now(UTC) - timedelta(hours=25)
        await db.flush()
        items2 = await fb_svc.list_feedbacks_for_invitation(
            db, viewer_user_id=a.id, invitation_id=inv.id
        )
        assert len(items2) == 2
