"""M13-08 meetup_event_service 单测."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError
from app.core.security import new_id
from app.models.user import User
from app.schemas.meetup import EventCreate, EventScoreSubmit
from app.services import meetup_event_service as event_svc


async def _make_user(db: AsyncSession, *, nickname: str = "u") -> User:
    u = User(
        id=new_id("usr"),
        wechat_openid=f"o_{new_id('mock')}",
        nickname=nickname,
        invite_code=new_id("inv")[-6:].upper(),
    )
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_create_event_requires_valid_template() -> None:
    async with AsyncSessionLocal() as db:
        org = await _make_user(db)
        with pytest.raises(BadRequestError) as exc:
            await event_svc.create_event(
                db,
                organizer_user_id=org.id,
                payload=EventCreate(
                    title="测试",
                    template_code="invalid_template",
                ),
            )
        assert exc.value.code == 40052


@pytest.mark.asyncio
async def test_three_templates_create_open_event() -> None:
    async with AsyncSessionLocal() as db:
        org = await _make_user(db)
        for code in (
            "putting_contest",
            "distance_contest",
            "overall_score",
        ):
            event = await event_svc.create_event(
                db,
                organizer_user_id=org.id,
                payload=EventCreate(
                    title=f"{code} 挑战",
                    template_code=code,
                ),
            )
            assert event.status == "open"
            assert event.template_code == code
            assert event.capacity == 8


@pytest.mark.asyncio
async def test_join_full_event_returns_42910() -> None:
    async with AsyncSessionLocal() as db:
        org = await _make_user(db)
        event = await event_svc.create_event(
            db,
            organizer_user_id=org.id,
            payload=EventCreate(
                title="满员测试",
                template_code="putting_contest",
                capacity=2,
            ),
        )
        u1 = await _make_user(db, nickname="u1")
        u2 = await _make_user(db, nickname="u2")
        u3 = await _make_user(db, nickname="u3")
        await event_svc.join_event(db, event_id=event.id, user_id=u1.id)
        await event_svc.join_event(db, event_id=event.id, user_id=u2.id)
        with pytest.raises(BadRequestError) as exc:
            await event_svc.join_event(db, event_id=event.id, user_id=u3.id)
        assert exc.value.code == 42910


@pytest.mark.asyncio
async def test_submit_score_awards_honor_badge_and_leaderboard() -> None:
    async with AsyncSessionLocal() as db:
        org = await _make_user(db)
        p1 = await _make_user(db, nickname="p1")
        p2 = await _make_user(db, nickname="p2")
        event = await event_svc.create_event(
            db,
            organizer_user_id=org.id,
            payload=EventCreate(
                title="推杆赛",
                template_code="putting_contest",
            ),
        )
        await event_svc.join_event(db, event_id=event.id, user_id=p1.id)
        await event_svc.join_event(db, event_id=event.id, user_id=p2.id)
        await event_svc.submit_score(
            db,
            event_id=event.id,
            user_id=p1.id,
            payload=EventScoreSubmit(self_reported_score=7),
        )
        await event_svc.submit_score(
            db,
            event_id=event.id,
            user_id=p2.id,
            payload=EventScoreSubmit(self_reported_score=9),
        )
        board = await event_svc.build_leaderboard(db, event_id=event.id)
        assert len(board) == 2
        assert board[0]["user_id"] == p2.id
        assert board[0]["rank"] == 1
        badges = (event.moderation_payload or {}).get("completion_badges") or {}
        assert p1.id in badges
        assert badges[p1.id]["honor_only"] is True
        assert "reward_cash" not in badges[p1.id]
        assert "reward_item" not in badges[p1.id]


@pytest.mark.asyncio
async def test_overall_score_leaderboard_asc() -> None:
    async with AsyncSessionLocal() as db:
        org = await _make_user(db)
        a = await _make_user(db, nickname="a")
        b = await _make_user(db, nickname="b")
        event = await event_svc.create_event(
            db,
            organizer_user_id=org.id,
            payload=EventCreate(
                title="18 洞",
                template_code="overall_score",
            ),
        )
        await event_svc.join_event(db, event_id=event.id, user_id=a.id)
        await event_svc.join_event(db, event_id=event.id, user_id=b.id)
        await event_svc.submit_score(
            db,
            event_id=event.id,
            user_id=a.id,
            payload=EventScoreSubmit(self_reported_score=88),
        )
        await event_svc.submit_score(
            db,
            event_id=event.id,
            user_id=b.id,
            payload=EventScoreSubmit(self_reported_score=82),
        )
        board = await event_svc.build_leaderboard(db, event_id=event.id)
        assert board[0]["user_id"] == b.id
