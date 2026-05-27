"""M13-02 GET /v1/venues/{nearby,id} 端点 + flag 守门测试."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.user import User
from app.schemas.meetup import VenueCreate
from app.services import meetup_service


async def _seed_user_and_venues() -> tuple[str, str]:
    """种子 1 个用户 + 1 个 active venue（39.9,116.4）+ 1 个 closed venue."""

    async with AsyncSessionLocal() as db:
        u = User(
            id=new_id("usr"),
            wechat_openid=f"o_{new_id('mock')}",
            nickname="t",
            invite_code=new_id("inv")[-6:].upper(),
        )
        db.add(u)
        await db.flush()

        active = await meetup_service.create_venue(
            db,
            payload=VenueCreate(
                city="北京",
                name="测试场地（active）",
                venue_type="indoor_range",
                latitude=39.9042,
                longitude=116.4074,
            ),
            contributor_user_id=u.id,
        )
        closed = await meetup_service.create_venue(
            db,
            payload=VenueCreate(
                city="北京",
                name="测试场地（closed）",
                venue_type="indoor_range",
                latitude=39.9042,
                longitude=116.4074,
            ),
            contributor_user_id=u.id,
        )
        closed.status = "closed"
        await db.commit()
        return active.id, closed.id


@pytest.fixture
def meetup_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_MEETUP_ENABLED", True)


@pytest.fixture
def meetup_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_MEETUP_ENABLED", False)


@pytest.mark.asyncio
async def test_nearby_404_when_flag_off(
    client: AsyncClient, meetup_disabled: None
) -> None:
    resp = await client.get("/v1/venues/nearby?lat=39.9&lng=116.4")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_detail_404_when_flag_off(
    client: AsyncClient, meetup_disabled: None
) -> None:
    resp = await client.get("/v1/venues/ven_anything")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_nearby_returns_active_with_distance(
    client: AsyncClient, meetup_enabled: None
) -> None:
    active_id, _ = await _seed_user_and_venues()
    resp = await client.get(
        "/v1/venues/nearby?lat=39.9042&lng=116.4074&radius_km=5"
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    ids = {v["id"] for v in body["items"]}
    assert active_id in ids
    # 距离单调升序
    distances = [v["distance_km"] for v in body["items"]]
    assert distances == sorted(distances)
    # 中心点距离 < 0.5km
    me = [v for v in body["items"] if v["id"] == active_id][0]
    assert me["distance_km"] < 0.5
    # echo 字段回显
    assert body["center_latitude"] == 39.9042
    assert body["radius_km"] == 5.0


@pytest.mark.asyncio
async def test_nearby_excludes_closed_venue(
    client: AsyncClient, meetup_enabled: None
) -> None:
    active_id, closed_id = await _seed_user_and_venues()
    resp = await client.get(
        "/v1/venues/nearby?lat=39.9042&lng=116.4074&radius_km=5"
    )
    body = resp.json()["data"]
    ids = {v["id"] for v in body["items"]}
    assert active_id in ids
    assert closed_id not in ids


@pytest.mark.asyncio
async def test_nearby_validates_query_params(
    client: AsyncClient, meetup_enabled: None
) -> None:
    """FastAPI Query 层校验范围；超界应返 422（pydantic ValidationError）."""

    r1 = await client.get("/v1/venues/nearby?lat=200&lng=0")
    r2 = await client.get(
        f"/v1/venues/nearby?lat=0&lng=0&radius_km={meetup_service.MAX_NEARBY_RADIUS_KM + 1}"
    )
    assert r1.status_code == 422
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_detail_returns_active_404_closed(
    client: AsyncClient, meetup_enabled: None
) -> None:
    active_id, closed_id = await _seed_user_and_venues()
    r_active = await client.get(f"/v1/venues/{active_id}")
    r_closed = await client.get(f"/v1/venues/{closed_id}")
    r_missing = await client.get("/v1/venues/ven_nope_xxx")
    assert r_active.status_code == 200
    assert r_active.json()["data"]["name"] == "测试场地（active）"
    assert r_closed.status_code == 404
    assert r_missing.status_code == 404
