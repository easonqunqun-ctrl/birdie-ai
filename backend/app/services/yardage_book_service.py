"""M10-03 · 个人 yardage book 业务逻辑."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.analysis import SwingAnalysis
from app.models.user import User
from app.models.user_profile_v2 import UserClub
from app.schemas.yardage_book import (
    YardageBookClubItem,
    YardageBookResponse,
    YardageBookUpdateRequest,
)
from app.services import user_clubs_service
from app.services.yardage_inference import MIN_INFERENCE_SAMPLES, infer_yardage_for_club


async def _partial_sample_count(db: AsyncSession, *, user_id: str, club_type: str) -> int:
    stmt = select(func.count(SwingAnalysis.id)).where(
        SwingAnalysis.user_id == user_id,
        SwingAnalysis.club_type == club_type,
        SwingAnalysis.target_yardage.isnot(None),
        SwingAnalysis.deleted_at.is_(None),
    )
    return int((await db.execute(stmt)).scalar_one())


async def get_yardage_book(*, user: User, db: AsyncSession) -> YardageBookResponse:
    clubs = await user_clubs_service.list_clubs(db, user)
    items: list[YardageBookClubItem] = []
    for club in clubs:
        if club.self_yardage_m is not None:
            items.append(
                YardageBookClubItem(
                    club_id=club.id,
                    club_type=club.club_type,
                    nickname=club.nickname,
                    my_yards=club.self_yardage_m,
                    std_yards=None,
                    sample_count=0,
                    source="self",
                )
            )
            continue

        inferred = await infer_yardage_for_club(
            db, user_id=user.id, club_type=club.club_type
        )
        if inferred is None:
            partial = await _partial_sample_count(
                db, user_id=user.id, club_type=club.club_type
            )
            items.append(
                YardageBookClubItem(
                    club_id=club.id,
                    club_type=club.club_type,
                    nickname=club.nickname,
                    my_yards=None,
                    std_yards=None,
                    sample_count=min(partial, MIN_INFERENCE_SAMPLES - 1),
                    source="none",
                )
            )
        else:
            items.append(
                YardageBookClubItem(
                    club_id=club.id,
                    club_type=club.club_type,
                    nickname=club.nickname,
                    my_yards=inferred.avg,
                    std_yards=round(inferred.std, 1),
                    sample_count=inferred.sample_count,
                    source="inferred",
                )
            )
    return YardageBookResponse(clubs=items)


async def update_yardage_book(
    *,
    user: User,
    payload: YardageBookUpdateRequest,
    db: AsyncSession,
) -> YardageBookResponse:
    for item in payload.clubs:
        club = await db.get(UserClub, item.club_id)
        if club is None or club.user_id != user.id or not club.is_active:
            raise NotFoundError(message=f"装备 {item.club_id} 不存在")
        if item.self_yardage_m is not None and item.self_yardage_m > 400:
            raise BadRequestError(message="码数不能超过 400")
        club.self_yardage_m = item.self_yardage_m
    await db.flush()
    return await get_yardage_book(user=user, db=db)
