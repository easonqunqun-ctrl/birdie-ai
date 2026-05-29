"""M12-02 GET /v1/pros 读端点 + flag 守门测试.

覆盖
----
1. PHASE2_PROS_ENABLED=False → 三端点全部 404
2. flag=True + seed → list / detail / clips 正常
3. is_active=False 球手对所有端点不可见
4. clips 端 camera_angle 过滤生效
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.integrations.llm import FakeLLMClient
from app.models.pro_library import ProSwingClip
from app.schemas.pro_library import ProPlayerCreate
from app.services import pro_library_service as svc
from app.services import pro_pgc_service as pgc_svc


@pytest.fixture
def pros_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_PROS_ENABLED", True)


@pytest.fixture
def pros_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_PROS_ENABLED", False)


@pytest.mark.asyncio
async def test_list_pros_404_when_flag_off(
    client: AsyncClient, pros_disabled: None
) -> None:
    resp = await client.get("/v1/pros")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_pro_404_when_flag_off(
    client: AsyncClient, pros_disabled: None
) -> None:
    resp = await client.get("/v1/pros/pp_anything")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_clips_404_when_flag_off(
    client: AsyncClient, pros_disabled: None
) -> None:
    resp = await client.get("/v1/pros/pp_anything/clips")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_pros_returns_seeded(
    client: AsyncClient, pros_enabled: None
) -> None:
    async with AsyncSessionLocal() as db:
        await svc.seed_initial_pros(db)
        await db.commit()

    resp = await client.get("/v1/pros")
    assert resp.status_code == 200
    payload = resp.json()["data"]
    names = {p["name"] for p in payload}
    assert "Demo Pro · 内置示例" in names


@pytest.mark.asyncio
async def test_inactive_player_invisible_to_list_and_detail(
    client: AsyncClient, pros_enabled: None
) -> None:
    async with AsyncSessionLocal() as db:
        inactive = await svc.create_player(
            db,
            ProPlayerCreate(
                name="SoftDeleted",
                handedness="right",
                is_active=False,
            ),
        )
        await db.commit()
        inactive_id = inactive.id

    # 列表不出现
    r_list = await client.get("/v1/pros")
    assert r_list.status_code == 200
    assert all(p["id"] != inactive_id for p in r_list.json()["data"])

    # detail / clips 都 404（不暴露 id 的存在性）
    r_detail = await client.get(f"/v1/pros/{inactive_id}")
    r_clips = await client.get(f"/v1/pros/{inactive_id}/clips")
    assert r_detail.status_code == 404
    assert r_clips.status_code == 404


@pytest.mark.asyncio
async def test_get_clips_camera_angle_filter(
    client: AsyncClient, pros_enabled: None
) -> None:
    """face_on 过滤后只返 face_on 镜头；seed 默认 face_on 所以 face_on=1, down_the_line=0."""

    async with AsyncSessionLocal() as db:
        [player] = await svc.seed_initial_pros(db)
        await db.commit()
        pid = player.id

    r_face = await client.get(f"/v1/pros/{pid}/clips?camera_angle=face_on")
    r_dtl = await client.get(
        f"/v1/pros/{pid}/clips?camera_angle=down_the_line"
    )
    assert r_face.status_code == 200 and r_dtl.status_code == 200
    assert len(r_face.json()["data"]) == 1
    assert r_dtl.json()["data"] == []


@pytest.mark.asyncio
async def test_get_clips_returns_only_published(
    client: AsyncClient, pros_enabled: None
) -> None:
    """add_clip 默认 is_published=False；未 publish 的镜头不出现在 list."""

    from app.schemas.pro_library import ProSwingClipCreate

    async with AsyncSessionLocal() as db:
        [player] = await svc.seed_initial_pros(db)
        # 再插一个未发布的 clip
        await svc.add_clip(
            db,
            ProSwingClipCreate(
                pro_player_id=player.id,
                club_type="driver",
                camera_angle="face_on",
                video_url="https://example.com/draft.mp4",
                license_status="public_clip",
                source_credit="internal draft",
                source_url="https://example.com/draft-meta",
                is_published=False,
            ),
        )
        await db.commit()
        pid = player.id

    r = await client.get(f"/v1/pros/{pid}/clips")
    assert r.status_code == 200
    items = r.json()["data"]
    # 只应看到 seed 的 published clip，未发布的草稿不出现
    assert len(items) == 1
    assert items[0]["is_published"] is True


@pytest.mark.asyncio
async def test_get_current_topic_404_when_flag_off(
    client: AsyncClient, pros_disabled: None
) -> None:
    resp = await client.get("/v1/pros/topics/current")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_current_topic_null_when_empty(
    client: AsyncClient, pros_enabled: None
) -> None:
    resp = await client.get("/v1/pros/topics/current")
    assert resp.status_code == 200
    assert resp.json()["data"] is None


@pytest.mark.asyncio
async def test_get_current_topic_returns_seeded(
    client: AsyncClient, pros_enabled: None
) -> None:
    async with AsyncSessionLocal() as db:
        await svc.seed_initial_pros(db)
        await svc.seed_initial_weekly_topic(db)
        await db.commit()

    resp = await client.get("/v1/pros/topics/current")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data is not None
    assert data["code"] == "demo_weekly_m12"
    assert len(data["clips"]) >= 1
    assert data["clips"][0]["player"]["name"] == "Demo Pro · 内置示例"


@pytest.mark.asyncio
async def test_list_clip_annotations_returns_seeded(
    client: AsyncClient,
    pros_enabled: None,
) -> None:
    async with AsyncSessionLocal() as db:
        await svc.seed_initial_pros(db)
        await pgc_svc.seed_initial_pgc_annotations(db)
        clip = (
            await db.execute(
                select(ProSwingClip).where(ProSwingClip.is_published.is_(True))
            )
        ).scalar_one()
        await db.commit()
        clip_id = clip.id

    resp = await client.get(f"/v1/pros/clips/{clip_id}/annotations")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 3
    assert data[0]["annotation_type"] == "text"


@pytest.mark.asyncio
async def test_pgc_insight_requires_auth(
    client: AsyncClient, pros_enabled: None
) -> None:
    resp = await client.post("/v1/pros/clips/psc_any/pgc-insight", json={})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_pgc_insight_happy_path(
    client: AsyncClient,
    auth_headers: dict[str, str],
    pros_enabled: None,
    use_fake_llm: FakeLLMClient,
) -> None:
    use_fake_llm.set_reply("职业节奏更从容，你可对标上杆顶点。")
    async with AsyncSessionLocal() as db:
        await svc.seed_initial_pros(db)
        await pgc_svc.seed_initial_pgc_annotations(db)
        clip = (
            await db.execute(
                select(ProSwingClip).where(ProSwingClip.is_published.is_(True))
            )
        ).scalar_one()
        await db.commit()
        clip_id = clip.id

    resp = await client.post(
        f"/v1/pros/clips/{clip_id}/pgc-insight",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200, resp.text
    assert "职业节奏" in resp.json()["data"]["insight"]
