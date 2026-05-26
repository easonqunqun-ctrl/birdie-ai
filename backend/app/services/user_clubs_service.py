"""P2-M9-02 装备清单 CRUD service（对齐 kickoff §3.5 数据流）.

依赖 M9-01 PR #90：复用 `app.models.user_profile_v2.UserClub` + `MAX_CLUBS_PER_USER`。

错误码（kickoff §4.1）
----------------------
- 40020：装备清单 14 支上限（自定义 BadRequestError）
- 40021：球杆不存在 / 不属于当前用户（NotFoundError）

灰度
----
被 `PHASE2_PROFILE_V2_ENABLED` flag 守门（M9-01/03/04 共享）。API 路由层负责
门禁；service 不关心 flag，保证服务内部可测试。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.security import new_id
from app.models.user import User
from app.models.user_profile_v2 import MAX_CLUBS_PER_USER, UserClub
from app.schemas.user_club import UserClubCreate, UserClubUpdate

# 自定义业务错误码（kickoff §4.1）
ERR_CLUB_LIMIT_REACHED = 40020
ERR_CLUB_NOT_FOUND = 40021


async def list_clubs(db: AsyncSession, user: User) -> list[UserClub]:
    """按 sort_order ASC + created_at ASC 列出全部球杆（含 is_active=False）。

    UI 列表展示需要包含未启用球杆（用户能看到完整清单 + 切换启用状态）。
    """
    stmt = (
        select(UserClub)
        .where(UserClub.user_id == user.id)
        .order_by(UserClub.sort_order.asc(), UserClub.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_clubs(db: AsyncSession, user: User) -> int:
    """统计当前用户球杆数（用于上限校验 + 列表响应 total）。"""
    stmt = select(UserClub).where(UserClub.user_id == user.id)
    result = await db.execute(stmt)
    return len(list(result.scalars().all()))


async def add_club(
    db: AsyncSession,
    user: User,
    payload: UserClubCreate,
) -> UserClub:
    """新增球杆，超 14 支 → 40020。"""
    current_count = await count_clubs(db, user)
    if current_count >= MAX_CLUBS_PER_USER:
        raise BadRequestError(
            code=ERR_CLUB_LIMIT_REACHED,
            message=f"装备清单最多 {MAX_CLUBS_PER_USER} 支，请先删除不用的球杆",
            http_status=400,
        )

    club = UserClub(
        id=f"ucb_{new_id()[:20]}",  # ucb_<nanoid 20>
        user_id=user.id,
        club_type=payload.club_type,
        nickname=payload.nickname,
        self_yardage_m=payload.self_yardage_m,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    db.add(club)
    await db.flush()
    await db.refresh(club)
    return club


async def get_club(db: AsyncSession, user: User, club_id: str) -> UserClub:
    """按 id 查找并校验归属权；不存在或非本人 → 40021。"""
    stmt = select(UserClub).where(
        UserClub.id == club_id,
        UserClub.user_id == user.id,
    )
    result = await db.execute(stmt)
    club = result.scalar_one_or_none()
    if club is None:
        raise NotFoundError(
            code=ERR_CLUB_NOT_FOUND,
            message="球杆不存在或不属于您",
        )
    return club


async def update_club(
    db: AsyncSession,
    user: User,
    club_id: str,
    payload: UserClubUpdate,
) -> UserClub:
    """局部更新；未传字段保持原值。"""
    club = await get_club(db, user, club_id)
    update_dict = payload.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(club, key, value)
    await db.flush()
    await db.refresh(club)
    return club


async def delete_club(db: AsyncSession, user: User, club_id: str) -> None:
    """硬删除（kickoff R-04：不影响 swing_analyses.club_type 历史报告，字符串字段无 FK）。"""
    club = await get_club(db, user, club_id)
    await db.delete(club)
    await db.flush()


__all__ = [
    "ERR_CLUB_LIMIT_REACHED",
    "ERR_CLUB_NOT_FOUND",
    "add_club",
    "count_clubs",
    "delete_club",
    "get_club",
    "list_clubs",
    "update_club",
]
