"""M13 约球端点共用守门（灰度 + M13-09 合规）."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.services import meetup_safety_service as safety_svc


def ensure_meetup_feature_enabled() -> None:
    if not settings.PHASE2_MEETUP_ENABLED:
        raise NotFoundError(code=40406, message="约球功能未开放")


async def ensure_meetup_user_ready(db: AsyncSession, *, user: User) -> None:
    ensure_meetup_feature_enabled()
    await safety_svc.ensure_meetup_access(db, user=user)
