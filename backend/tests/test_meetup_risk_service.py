"""M13-06 · meetup_risk_service / user_credit_service 单测."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import (
    MeetupCreditTooLowError,
    MeetupInviteCooldownError,
    MeetupInviteLimitError,
)
from app.core.security import new_id
from app.models.user import User
from app.schemas.meetup import InvitationCreate
from app.services import meetup_risk_service as risk_svc
from app.services import meetup_service as meetup_svc
from app.services import user_credit_service as credit_svc


class FakeRedis:
    """内存 Redis 桩：覆盖 M13-06 用到的命令."""

    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.ttl: dict[str, int] = {}

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    async def hset(self, key: str, mapping: dict[str, str]) -> None:
        self.hashes.setdefault(key, {}).update(mapping)

    async def delete(self, key: str) -> None:
        self.kv.pop(key, None)
        self.hashes.pop(key, None)

    async def exists(self, key: str) -> int:
        return 1 if key in self.kv else 0

    async def get(self, key: str) -> str | None:
        return self.kv.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.kv[key] = value
        self.ttl[key] = ttl

    async def incr(self, key: str) -> int:
        cur = int(self.kv.get(key, "0")) + 1
        self.kv[key] = str(cur)
        return cur

    async def expire(self, key: str, ttl: int) -> None:
        self.ttl[key] = ttl


async def _make_user(
    db: AsyncSession, *, credit: int = 100, membership: str = "free"
) -> User:
    u = User(
        id=new_id("usr"),
        wechat_openid=f"o_{new_id('mock')}",
        nickname="t",
        invite_code=new_id("inv")[-6:].upper(),
        meetup_credit_score=credit,
        membership_type=membership,
    )
    db.add(u)
    await db.flush()
    return u


def test_credit_delta_from_feedback_tags() -> None:
    assert credit_svc.credit_delta_from_feedback(rating=5, tags=["on_time"]) == 12
    assert credit_svc.credit_delta_from_feedback(rating=1, tags=["no_show"]) == -22


def test_assert_credit_allows_invite_blocks_low_score() -> None:
    user = User(
        id="usr_x",
        invite_code="ABC123",
        meetup_credit_score=50,
    )
    with pytest.raises(MeetupCreditTooLowError):
        credit_svc.assert_credit_allows_invite(user, min_score=60)


@pytest.mark.asyncio
async def test_daily_invite_limit_free_user() -> None:
    redis = FakeRedis()
    async with AsyncSessionLocal() as db:
        inviter = await _make_user(db)
        invitee = await _make_user(db)
        await risk_svc.set_risk_config_override(
            redis, daily_limit_free=1, daily_limit_member=10
        )

        cfg = await risk_svc.assert_can_send_invitation(db, redis, user=inviter)
        assert cfg.daily_limit_free == 1

        inv = await meetup_svc.create_invitation(
            db,
            inviter_user_id=inviter.id,
            payload=InvitationCreate(invitee_user_id=invitee.id),
        )
        await risk_svc.finalize_invitation_sent(
            db, redis, invitation=inv, inviter=inviter, config=cfg
        )

        with pytest.raises(MeetupInviteLimitError) as exc:
            await risk_svc.assert_can_send_invitation(db, redis, user=inviter)
        assert exc.value.code == 42920


@pytest.mark.asyncio
async def test_accept_rate_triggers_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(settings, "MEETUP_RISK_ACCEPT_RATE_MIN_SAMPLES", 2)
    monkeypatch.setattr(settings, "MEETUP_RISK_ACCEPT_RATE_THRESHOLD", 0.5)

    async with AsyncSessionLocal() as db:
        inviter = await _make_user(db)
        others = [await _make_user(db) for _ in range(3)]

        for idx, invitee in enumerate(others[:2]):
            inv = await meetup_svc.create_invitation(
                db,
                inviter_user_id=inviter.id,
                payload=InvitationCreate(invitee_user_id=invitee.id),
            )
            if idx == 0:
                inv.status = "accepted"
            else:
                inv.status = "declined"
        await db.flush()

        with pytest.raises(MeetupInviteCooldownError) as exc:
            await risk_svc.assert_can_send_invitation(db, redis, user=inviter)
        assert exc.value.code == 42921


@pytest.mark.asyncio
async def test_consecutive_declines_apply_cooldown() -> None:
    redis = FakeRedis()
    cfg = risk_svc.MeetupRiskConfig(consecutive_decline_limit=2, cooldown_hours=1)
    inviter_id = "usr_inv"

    await risk_svc.on_invitation_declined(
        redis, inviter_user_id=inviter_id, config=cfg
    )
    await risk_svc.on_invitation_declined(
        redis, inviter_user_id=inviter_id, config=cfg
    )
    assert await redis.exists(f"{risk_svc.REDIS_COOLDOWN_PREFIX}{inviter_id}") == 1
