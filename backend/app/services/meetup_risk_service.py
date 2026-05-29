"""M13-06 · 约球风控：邀请上限 / 接受率 / 冷却 / 信用分."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import MeetupInviteCooldownError, MeetupInviteLimitError
from app.core.logging import get_logger
from app.models.meetup import MeetupInvitation
from app.models.user import User
from app.services import user_credit_service as credit_svc

logger = get_logger("meetup_risk")

REDIS_CONFIG_KEY = "meetup:risk:config"
REDIS_COOLDOWN_PREFIX = "meetup:risk:cooldown:"
REDIS_DAILY_PREFIX = "meetup:risk:invite_daily:"
REDIS_DECLINE_STREAK_PREFIX = "meetup:risk:decline_streak:"


@dataclass(frozen=True)
class MeetupRiskConfig:
    daily_limit_free: int = 5
    daily_limit_member: int = 10
    accept_rate_threshold: float = 0.10
    accept_rate_min_samples: int = 10
    consecutive_decline_limit: int = 3
    cooldown_hours: int = 24
    credit_min_to_invite: int = 60


def _china_date_key() -> str:
    return (datetime.now(UTC) + timedelta(hours=8)).date().isoformat()


def _is_active_member(user: User) -> bool:
    if user.membership_type == "free":
        return False
    exp = user.membership_expires_at
    if exp is None:
        return True
    return exp > datetime.now(UTC)


def _config_from_settings() -> MeetupRiskConfig:
    return MeetupRiskConfig(
        daily_limit_free=settings.MEETUP_RISK_DAILY_LIMIT_FREE,
        daily_limit_member=settings.MEETUP_RISK_DAILY_LIMIT_MEMBER,
        accept_rate_threshold=settings.MEETUP_RISK_ACCEPT_RATE_THRESHOLD,
        accept_rate_min_samples=settings.MEETUP_RISK_ACCEPT_RATE_MIN_SAMPLES,
        consecutive_decline_limit=settings.MEETUP_RISK_CONSECUTIVE_DECLINE_LIMIT,
        cooldown_hours=settings.MEETUP_RISK_COOLDOWN_HOURS,
        credit_min_to_invite=settings.MEETUP_RISK_CREDIT_MIN_TO_INVITE,
    )


async def get_risk_config(redis: Redis) -> MeetupRiskConfig:
    """读取风控阈值：Redis hash 覆盖 env 默认（运营可热更新）."""

    base = _config_from_settings()
    raw = await redis.hgetall(REDIS_CONFIG_KEY)
    if not raw:
        return base
    merged = asdict(base)
    for key in merged:
        if key not in raw:
            continue
        val = raw[key]
        if isinstance(merged[key], int):
            merged[key] = int(val)
        elif isinstance(merged[key], float):
            merged[key] = float(val)
    return MeetupRiskConfig(**merged)


async def set_risk_config_override(redis: Redis, **overrides: int | float) -> MeetupRiskConfig:
    """测试 / 运维：写入 Redis 阈值覆盖."""

    if not overrides:
        await redis.delete(REDIS_CONFIG_KEY)
        return _config_from_settings()
    payload = {k: str(v) for k, v in overrides.items()}
    await redis.hset(REDIS_CONFIG_KEY, mapping=payload)
    return await get_risk_config(redis)


async def _is_in_cooldown(redis: Redis, user_id: str) -> bool:
    return bool(await redis.exists(f"{REDIS_COOLDOWN_PREFIX}{user_id}"))


async def _apply_cooldown(redis: Redis, user_id: str, *, hours: int) -> None:
    ttl = max(1, hours * 3600)
    await redis.setex(f"{REDIS_COOLDOWN_PREFIX}{user_id}", ttl, "1")
    logger.info("meetup_risk_cooldown_applied", user_id=user_id, hours=hours)


async def _daily_invite_count(redis: Redis, user_id: str) -> int:
    key = f"{REDIS_DAILY_PREFIX}{user_id}:{_china_date_key()}"
    raw = await redis.get(key)
    return int(raw or 0)


async def _incr_daily_invite_count(redis: Redis, user_id: str) -> int:
    key = f"{REDIS_DAILY_PREFIX}{user_id}:{_china_date_key()}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 48 * 3600)
    return int(count)


async def compute_inviter_accept_rate(
    db: AsyncSession, *, inviter_user_id: str
) -> tuple[int, float | None]:
    """返回 (已发起数, 接受率)；样本不足时 accept_rate=None."""

    sent_stmt = select(func.count()).where(
        MeetupInvitation.inviter_user_id == inviter_user_id,
        MeetupInvitation.status != "cancelled",
    )
    sent = int((await db.execute(sent_stmt)).scalar_one())

    accepted_stmt = select(func.count()).where(
        MeetupInvitation.inviter_user_id == inviter_user_id,
        MeetupInvitation.status == "accepted",
    )
    accepted = int((await db.execute(accepted_stmt)).scalar_one())
    if sent == 0:
        return 0, None
    return sent, accepted / sent


async def assert_can_send_invitation(
    db: AsyncSession, redis: Redis, *, user: User
) -> MeetupRiskConfig:
    """发起邀请前风控校验；通过则返回当前 config（供 risk_payload 快照）."""

    cfg = await get_risk_config(redis)

    credit_svc.assert_credit_allows_invite(
        user, min_score=cfg.credit_min_to_invite
    )

    if await _is_in_cooldown(redis, user.id):
        raise MeetupInviteCooldownError(
            detail="cooldown_active",
        )

    sent, accept_rate = await compute_inviter_accept_rate(db, inviter_user_id=user.id)
    if (
        sent >= cfg.accept_rate_min_samples
        and accept_rate is not None
        and accept_rate < cfg.accept_rate_threshold
    ):
        await _apply_cooldown(redis, user.id, hours=cfg.cooldown_hours)
        raise MeetupInviteCooldownError(
            detail=f"accept_rate={accept_rate:.2f}, sent={sent}",
        )

    daily_limit = (
        cfg.daily_limit_member
        if _is_active_member(user)
        else cfg.daily_limit_free
    )
    used = await _daily_invite_count(redis, user.id)
    if used >= daily_limit:
        raise MeetupInviteLimitError(
            detail=f"used={used}, limit={daily_limit}",
        )

    return cfg


def build_risk_snapshot(config: MeetupRiskConfig, *, user: User, daily_used: int) -> dict:
    return {
        "daily_count": daily_used + 1,
        "credit_score": credit_svc.get_meetup_credit_score(user),
        "config": asdict(config),
        "checked_at": datetime.now(UTC).isoformat(),
    }


async def finalize_invitation_sent(
    db: AsyncSession,
    redis: Redis,
    *,
    invitation: MeetupInvitation,
    inviter: User,
    config: MeetupRiskConfig,
) -> None:
    count = await _incr_daily_invite_count(redis, invitation.inviter_user_id)
    invitation.risk_payload = build_risk_snapshot(
        config, user=inviter, daily_used=count - 1
    )
    await db.flush()


async def on_invitation_accepted(redis: Redis, *, inviter_user_id: str) -> None:
    await redis.delete(f"{REDIS_DECLINE_STREAK_PREFIX}{inviter_user_id}")


async def on_invitation_declined(
    redis: Redis,
    *,
    inviter_user_id: str,
    config: MeetupRiskConfig | None = None,
) -> None:
    cfg = config or _config_from_settings()
    key = f"{REDIS_DECLINE_STREAK_PREFIX}{inviter_user_id}"
    streak = await redis.incr(key)
    await redis.expire(key, cfg.cooldown_hours * 3600)
    if streak >= cfg.consecutive_decline_limit:
        await _apply_cooldown(redis, inviter_user_id, hours=cfg.cooldown_hours)
        await redis.delete(key)
        logger.info(
            "meetup_risk_decline_streak_cooldown",
            inviter_user_id=inviter_user_id,
            streak=streak,
        )


__all__ = [
    "MeetupRiskConfig",
    "assert_can_send_invitation",
    "compute_inviter_accept_rate",
    "finalize_invitation_sent",
    "get_risk_config",
    "on_invitation_accepted",
    "on_invitation_declined",
    "set_risk_config_override",
]
