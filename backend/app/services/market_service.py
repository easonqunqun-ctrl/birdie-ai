"""国内 / 国外市场分流与欢迎包（docs/01 §2.2.1）。

各市场前 ``WELCOME_USER_CAP`` 名用户各获 ``WELCOME_ANALYSES`` 次终身分析。
"""

from __future__ import annotations

from typing import Literal

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.locale import reply_locale_from_accept_language
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.user import MarketOffer

logger = get_logger("market")

Market = Literal["cn", "intl"]
Policy = Literal["welcome", "standard"]


def welcome_user_cap() -> int:
    return max(0, int(settings.WELCOME_USER_CAP))


def welcome_analyses() -> int:
    return max(0, int(settings.WELCOME_ANALYSES))


def classify_market(
    *,
    force_cn: bool = False,
    header: str | None = None,
    accept_language: str | None = None,
) -> Market:
    if force_cn:
        return "cn"
    raw = (header or "").strip().lower()
    if raw in ("cn", "intl"):
        return raw  # type: ignore[return-value]
    if reply_locale_from_accept_language(accept_language) == "en":
        return "intl"
    return "cn"


def market_from_request(request: Request | None, *, force_cn: bool = False) -> Market:
    if request is None:
        return classify_market(force_cn=force_cn)
    return classify_market(
        force_cn=force_cn,
        header=request.headers.get("x-app-market"),
        accept_language=request.headers.get("accept-language"),
    )


def is_cn_free(_user: User) -> bool:
    """已废弃：国内不再不限次。保留给旧调用方，恒为 False。"""
    return False


def offer_for(user: User) -> MarketOffer:
    market: Market = user.market if user.market in ("cn", "intl") else "cn"
    if user.intl_welcome_granted and user.intl_welcome_remaining > 0:
        policy: Policy = "welcome"
    else:
        policy = "standard"
    remaining = user.intl_welcome_remaining if user.intl_welcome_granted else None
    return MarketOffer(
        market=market,
        policy=policy,
        intl_welcome_remaining=remaining,
        intl_welcome_total=welcome_analyses(),
    )


async def ensure_user_market(
    db: AsyncSession,
    user: User,
    *,
    request: Request | None = None,
    force_cn: bool = False,
    redis: Redis | None = None,
) -> User:
    """首次写入 market（粘性）；各市场尝试占用欢迎包名额。"""
    if user.market not in ("cn", "intl"):
        if force_cn or user.wechat_openid or user.wechat_app_openid:
            user.market = "cn"
        else:
            user.market = market_from_request(request, force_cn=force_cn)
        logger.info(
            "user_market_assigned",
            extra={"user_id": user.id, "market": user.market},
        )
    if not user.intl_welcome_granted:
        await _try_grant_welcome(db, user, redis=redis)
    await db.flush()
    return user


async def _welcome_count_from_db(db: AsyncSession, market: str) -> int:
    stmt = select(func.count()).select_from(User).where(
        User.intl_welcome_granted.is_(True),
        User.market == market,
        User.deleted_at.is_(None),
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def _try_grant_welcome(
    db: AsyncSession,
    user: User,
    *,
    redis: Redis | None,
) -> None:
    cap = welcome_user_cap()
    grant_n = welcome_analyses()
    market = user.market if user.market in ("cn", "intl") else "cn"
    if cap <= 0 or grant_n <= 0 or user.intl_welcome_granted:
        return

    key = f"welcome:granted:{market}"
    if redis is not None:
        if await redis.get(key) is None:
            await redis.set(key, await _welcome_count_from_db(db, market), nx=True)
        n = int(await redis.incr(key))
        if n > cap:
            return
    else:
        if await _welcome_count_from_db(db, market) >= cap:
            return

    user.intl_welcome_granted = True
    user.intl_welcome_remaining = grant_n
    logger.info(
        "welcome_granted",
        extra={"user_id": user.id, "market": market, "remaining": grant_n},
    )
