"""M12-10 · 职业镜头收藏 / 想试试看训练任务."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import new_id
from app.models.pro_library import ProPlayer, ProSwingClip, UserProFavorite
from app.models.training import TrainingTask
from app.services import pro_library_service as pro_svc
from app.services.training_service import _china_today, ensure_current_week_plan, week_bounds

log = logging.getLogger(__name__)

# 对照球手挥杆：复用半挥杆 drill（与 issue 驱动计划共用动作库，避免新增 seed）
PRO_TRY_IT_DRILL_ID = "drill_half_swing"
TRY_IT_DEADLINE_DAYS = 3


async def list_user_favorites(
    db: AsyncSession, *, user_id: str
) -> list[tuple[UserProFavorite, ProSwingClip, ProPlayer]]:
    """按收藏时间倒序返回镜头 + 球手；下架镜头仍保留收藏记录."""

    rows = await db.execute(
        select(UserProFavorite, ProSwingClip, ProPlayer)
        .join(ProSwingClip, ProSwingClip.id == UserProFavorite.clip_id)
        .join(ProPlayer, ProPlayer.id == ProSwingClip.pro_player_id)
        .where(UserProFavorite.user_id == user_id)
        .order_by(UserProFavorite.created_at.desc())
    )
    return list(rows.all())


async def is_clip_favorited(db: AsyncSession, *, user_id: str, clip_id: str) -> bool:
    row = await db.execute(
        select(UserProFavorite.user_id).where(
            UserProFavorite.user_id == user_id,
            UserProFavorite.clip_id == clip_id,
        )
    )
    return row.scalar_one_or_none() is not None


async def create_try_it_task(
    db: AsyncSession, *, user_id: str, clip_id: str
) -> tuple[TrainingTask, bool]:
    """为收藏镜头生成「对照球手挥杆」训练任务.

    - 自动收藏（若尚未收藏）
    - 同 clip 已有 pending 任务 → 幂等返回（R-01 / R-02）
    - 返回 ``(task, created_new)``
    """

    clip = await pro_svc.get_clip(db, clip_id)
    if clip is None or not clip.is_published:
        raise NotFoundError(code=40406, message="镜头不存在或已下架")

    player = await pro_svc.get_player(db, clip.pro_player_id)
    if player is None or not player.is_active:
        raise NotFoundError(code=40406, message="球手不存在或已下架")

    fav_row = await db.execute(
        select(UserProFavorite).where(
            UserProFavorite.user_id == user_id,
            UserProFavorite.clip_id == clip_id,
        )
    )
    fav = fav_row.scalar_one_or_none()
    if fav is None:
        fav = await pro_svc.favorite_clip(db, user_id=user_id, clip_id=clip_id)

    if fav.training_task_id:
        existing = await db.get(TrainingTask, fav.training_task_id)
        if existing is not None and existing.user_id == user_id and existing.status == "pending":
            return existing, False

    today = _china_today()
    _, sunday = week_bounds(today)
    scheduled = min(today + timedelta(days=TRY_IT_DEADLINE_DAYS), sunday)

    plan = await ensure_current_week_plan(db, user_id)
    sort_order = len(plan.tasks or [])
    task = TrainingTask(
        id=new_id("task"),
        plan_id=plan.id,
        user_id=user_id,
        drill_id=PRO_TRY_IT_DRILL_ID,
        scheduled_date=scheduled,
        sort_order=sort_order,
        status="pending",
    )
    db.add(task)
    plan.total_tasks = (plan.total_tasks or 0) + 1

    fav.training_task_id = task.id
    await db.flush()

    log.info(
        "pro_try_it_task_created",
        extra={
            "user_id": user_id,
            "clip_id": clip_id,
            "task_id": task.id,
            "player_name": player.name,
        },
    )
    return task, True


async def load_pro_clip_refs_for_tasks(
    db: AsyncSession, *, user_id: str, task_ids: list[str]
) -> dict[str, tuple[str, str, bool]]:
    """task_id → (pro_clip_id, player_name_zh, clip_published)."""

    if not task_ids:
        return {}

    rows = await db.execute(
        select(
            UserProFavorite.training_task_id,
            UserProFavorite.clip_id,
            ProPlayer.name,
            ProSwingClip.is_published,
        )
        .join(ProSwingClip, ProSwingClip.id == UserProFavorite.clip_id)
        .join(ProPlayer, ProPlayer.id == ProSwingClip.pro_player_id)
        .where(
            UserProFavorite.user_id == user_id,
            UserProFavorite.training_task_id.in_(task_ids),
        )
    )
    out: dict[str, tuple[str, str, bool]] = {}
    for task_id, clip_id, player_name, is_published in rows.all():
        if task_id:
            out[task_id] = (clip_id, player_name, bool(is_published))
    return out


__all__ = [
    "PRO_TRY_IT_DRILL_ID",
    "create_try_it_task",
    "is_clip_favorited",
    "list_user_favorites",
    "load_pro_clip_refs_for_tasks",
]
