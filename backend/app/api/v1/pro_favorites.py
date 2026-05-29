"""M12-10 · 职业镜头收藏 / 想试试看 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.pro_library import (
    ProFavoriteCreate,
    ProFavoriteItemRead,
    ProPlayerRead,
    ProSwingClipRead,
    ProTryItResponse,
)
from app.services import pro_favorites_service as fav_svc
from app.services import pro_library_service as pro_svc

router = APIRouter()


def _ensure_pros_enabled() -> None:
    if not settings.PHASE2_PROS_ENABLED:
        raise NotFoundError(code=40406, message="球手对比库未开放")


def _favorite_to_read(
    fav,
    clip,
    player,
) -> ProFavoriteItemRead:
    unavailable = not clip.is_published or not player.is_active
    return ProFavoriteItemRead(
        clip_id=fav.clip_id,
        note=fav.note,
        training_task_id=fav.training_task_id,
        created_at=fav.created_at,
        clip=ProSwingClipRead.model_validate(clip),
        player=ProPlayerRead.model_validate(player),
        clip_unavailable=unavailable,
    )


@router.get(
    "/pros/favorites",
    summary="列出我的职业镜头收藏（M12-10）",
    response_model=APIResponse[list[ProFavoriteItemRead]],
)
async def list_my_pro_favorites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_pros_enabled()
    rows = await fav_svc.list_user_favorites(db, user_id=user.id)
    return ok([_favorite_to_read(f, c, p) for f, c, p in rows])


@router.post(
    "/pros/favorites",
    summary="收藏职业镜头（M12-10）",
    response_model=APIResponse[ProFavoriteItemRead],
)
async def add_pro_favorite(
    body: ProFavoriteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_pros_enabled()
    fav = await pro_svc.favorite_clip(
        db, user_id=user.id, clip_id=body.clip_id, note=body.note
    )
    clip = await pro_svc.get_clip(db, body.clip_id)
    player = await pro_svc.get_player(db, clip.pro_player_id) if clip else None
    if clip is None or player is None:
        raise NotFoundError(code=40406, message="镜头不存在")
    await db.commit()
    return ok(_favorite_to_read(fav, clip, player))


@router.delete(
    "/pros/favorites/{clip_id}",
    summary="取消收藏职业镜头（M12-10）",
    response_model=APIResponse[dict],
)
async def remove_pro_favorite(
    clip_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_pros_enabled()
    await pro_svc.unfavorite_clip(db, user_id=user.id, clip_id=clip_id)
    await db.commit()
    return ok({})


@router.post(
    "/pros/favorites/{clip_id}/try-it",
    summary="想试试看 · 生成对照球手训练任务（M12-10）",
    response_model=APIResponse[ProTryItResponse],
)
async def try_it_pro_clip(
    clip_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _ensure_pros_enabled()
    task, created = await fav_svc.create_try_it_task(
        db, user_id=user.id, clip_id=clip_id
    )
    await db.commit()
    return ok(ProTryItResponse(training_task_id=task.id, created=created))
