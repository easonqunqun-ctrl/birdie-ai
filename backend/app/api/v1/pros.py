"""二期 M12 球手对比库公开读端点（对齐 docs/23 §8.1 · M12-02）.

只暴露**已发布**的球手 / 镜头给小程序：
- ``GET /v1/pros`` — 列出 ``is_active=True`` 的球手
- ``GET /v1/pros/{player_id}`` — 单球手详情
- ``GET /v1/pros/{player_id}/clips?camera_angle=...`` — 该球手的 published clips

灰度
----
``PHASE2_PROS_ENABLED=False`` 时所有端点返回 ``404``，与 M11 / M9 守门同模式
（kickoff §4.2）。

写端点 / 收藏 / 匹配
-------------------
本路由仅交付读端点。匹配见 ``GET /v1/analyses/{id}/pro-matches``（M12-04）；
``favorite_clip`` / 收藏列表等按需后续 PR；M12-05（PGC 解说）按需扩展。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas.base import APIResponse, ok
from app.schemas.pro_library import (
    CameraAngleLiteral,
    ProPlayerRead,
    ProSwingClipRead,
)
from app.services import pro_library_service

router = APIRouter()


def _ensure_pros_enabled() -> None:
    """守门：未启用 PHASE2_PROS_ENABLED 直接 404."""

    if not settings.PHASE2_PROS_ENABLED:
        raise NotFoundError(code=40406, message="球手对比库未开放")


@router.get(
    "",
    summary="列出可用球手（M12-02）",
    response_model=APIResponse[list[ProPlayerRead]],
)
async def list_players(
    db: AsyncSession = Depends(get_db),
):
    """返回所有 ``is_active=True`` 的球手，按 ``sort_order`` / ``name`` 升序.

    版权下架 / 合作终止后用 ``is_active=False`` 软隔离，列表不再可见。
    """

    _ensure_pros_enabled()
    players = await pro_library_service.list_active_players(db)
    return ok([ProPlayerRead.model_validate(p) for p in players])


@router.get(
    "/{player_id}",
    summary="获取单球手详情（M12-02）",
    response_model=APIResponse[ProPlayerRead],
)
async def get_player_detail(
    player_id: str,
    db: AsyncSession = Depends(get_db),
):
    _ensure_pros_enabled()
    player = await pro_library_service.get_player(db, player_id)
    if player is None or not player.is_active:
        raise NotFoundError(code=40406, message="球手不存在或已下架")
    return ok(ProPlayerRead.model_validate(player))


@router.get(
    "/{player_id}/clips",
    summary="列出该球手已发布的镜头（M12-02）",
    response_model=APIResponse[list[ProSwingClipRead]],
)
async def list_player_clips(
    player_id: str,
    camera_angle: CameraAngleLiteral | None = Query(
        None, description="可选机位过滤；默认全部机位"
    ),
    club_type: str | None = Query(
        None, max_length=20, description="可选球杆类型过滤"
    ),
    db: AsyncSession = Depends(get_db),
):
    """该球手下所有 ``is_published=True`` 的镜头.

    球手不存在 / 软下架 → 404（不暴露 player_id 的存在性）。
    """

    _ensure_pros_enabled()
    player = await pro_library_service.get_player(db, player_id)
    if player is None or not player.is_active:
        raise NotFoundError(code=40406, message="球手不存在或已下架")

    clips = await pro_library_service.list_published_clips(
        db,
        player_id=player_id,
        club_type=club_type,
    )
    if camera_angle is not None:
        clips = [c for c in clips if c.camera_angle == camera_angle]
    return ok([ProSwingClipRead.model_validate(c) for c in clips])
