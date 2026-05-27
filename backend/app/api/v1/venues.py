"""二期 M13 球友约球 venue 端点（对齐 docs/23 §9.1 · M13-02）.

本 PR 仅暴露**读端**：
- ``GET /v1/venues/nearby?lat=&lng=&radius_km=&venue_type=&limit=`` —
  haversine 搜索附近 venue
- ``GET /v1/venues/{venue_id}`` — 单 venue 详情（含 lat/lng）

写端（创建 / flag）走 M13-03 + 后续 UGC 录入 PR；本 PR 不引入。

灰度
----
``PHASE2_MEETUP_ENABLED=False`` → 全部 404，与 M11 / M12 守门同模式。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.meetup import Venue
from app.schemas.base import APIResponse, ok
from app.schemas.meetup import (
    VenueNearbyItem,
    VenueNearbyResponse,
    VenueRead,
    VenueTypeLiteral,
)
from app.services import meetup_service

router = APIRouter()


def _ensure_meetup_enabled() -> None:
    if not settings.PHASE2_MEETUP_ENABLED:
        raise NotFoundError(code=40406, message="约球功能未开放")


@router.get(
    "/nearby",
    summary="附近场地搜索（haversine，M13-02）",
    response_model=APIResponse[VenueNearbyResponse],
)
async def get_nearby_venues(
    lat: float = Query(..., ge=-90, le=90, description="圆心纬度"),
    lng: float = Query(..., ge=-180, le=180, description="圆心经度"),
    radius_km: float = Query(
        5.0,
        gt=0,
        le=meetup_service.MAX_NEARBY_RADIUS_KM,
        description=f"搜索半径（km），上限 {meetup_service.MAX_NEARBY_RADIUS_KM}",
    ),
    venue_type: VenueTypeLiteral | None = Query(None, description="可选类型过滤"),
    limit: int = Query(
        meetup_service.DEFAULT_NEARBY_LIMIT,
        ge=1,
        le=meetup_service.MAX_NEARBY_LIMIT,
    ),
    db: AsyncSession = Depends(get_db),
):
    """按距离升序返回半径内 active venues 及 distance_km."""

    _ensure_meetup_enabled()
    pairs = await meetup_service.search_nearby_venues(
        db,
        latitude=lat,
        longitude=lng,
        radius_km=radius_km,
        limit=limit,
        venue_type=venue_type,
    )
    items: list[VenueNearbyItem] = []
    for venue, distance in pairs:
        item = VenueNearbyItem.model_validate(venue)
        # 复刻一次只覆盖 distance_km 字段（model_validate 不会自动算）
        items.append(item.model_copy(update={"distance_km": round(distance, 3)}))

    return ok(
        VenueNearbyResponse(
            items=items,
            total=len(items),
            center_latitude=lat,
            center_longitude=lng,
            radius_km=radius_km,
        )
    )


@router.get(
    "/{venue_id}",
    summary="获取单 venue 详情（M13-02）",
    response_model=APIResponse[VenueRead],
)
async def get_venue_detail(
    venue_id: str,
    db: AsyncSession = Depends(get_db),
):
    _ensure_meetup_enabled()
    venue = await db.get(Venue, venue_id)
    if venue is None or venue.status != "active":
        raise NotFoundError(code=40406, message="场地不存在或已下架")
    return ok(VenueRead.model_validate(venue))
