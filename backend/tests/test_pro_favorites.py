"""M12-10 · pro_favorites_service / API 单测."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.user import User
from app.schemas.pro_library import ProPlayerCreate, ProSwingClipCreate
from app.services import pro_favorites_service as fav_svc
from app.services import pro_library_service as pro_svc
from app.services.training_service import get_current_week_plan


async def _make_user(db: AsyncSession) -> User:
    u = User(
        id=new_id("usr"),
        wechat_openid=f"o_{new_id('mock')}",
        nickname="t",
        invite_code=new_id("inv")[-6:].upper(),
    )
    db.add(u)
    await db.flush()
    return u


def _clip_payload(player_id: str, **overrides) -> ProSwingClipCreate:
    base = dict(
        pro_player_id=player_id,
        club_type="iron_7",
        camera_angle="face_on",
        video_url="https://example.com/x.mp4",
        license_status="public_clip",
        source_credit="Source: demo",
        source_url="https://example.com/src",
        is_published=True,
    )
    base.update(overrides)
    return ProSwingClipCreate(**base)


@pytest.mark.asyncio
async def test_try_it_creates_training_task_and_favorite() -> None:
    async with AsyncSessionLocal() as db:
        user = await _make_user(db)
        player = await pro_svc.create_player(
            db, ProPlayerCreate(name="Pro A", handedness="right")
        )
        clip = await pro_svc.add_clip(db, _clip_payload(player.id))
        task, created = await fav_svc.create_try_it_task(
            db, user_id=user.id, clip_id=clip.id
        )
        assert created is True
        assert task.status == "pending"
        assert task.drill_id == fav_svc.PRO_TRY_IT_DRILL_ID
        plan = await get_current_week_plan(db, user)
        assert plan is not None
        assert plan.total_tasks == 1
        favs = await fav_svc.list_user_favorites(db, user_id=user.id)
        assert len(favs) == 1
        assert favs[0][0].training_task_id == task.id


@pytest.mark.asyncio
async def test_try_it_is_idempotent_for_pending_task() -> None:
    async with AsyncSessionLocal() as db:
        user = await _make_user(db)
        player = await pro_svc.create_player(
            db, ProPlayerCreate(name="Pro B", handedness="right")
        )
        clip = await pro_svc.add_clip(db, _clip_payload(player.id))
        task1, created1 = await fav_svc.create_try_it_task(
            db, user_id=user.id, clip_id=clip.id
        )
        task2, created2 = await fav_svc.create_try_it_task(
            db, user_id=user.id, clip_id=clip.id
        )
        assert created1 is True
        assert created2 is False
        assert task1.id == task2.id
        plan = await get_current_week_plan(db, user)
        assert plan is not None
        assert plan.total_tasks == 1


@pytest.mark.asyncio
async def test_load_pro_clip_refs_for_tasks() -> None:
    async with AsyncSessionLocal() as db:
        user = await _make_user(db)
        player = await pro_svc.create_player(
            db, ProPlayerCreate(name="Pro C", handedness="left")
        )
        clip = await pro_svc.add_clip(db, _clip_payload(player.id))
        task, _ = await fav_svc.create_try_it_task(
            db, user_id=user.id, clip_id=clip.id
        )
        refs = await fav_svc.load_pro_clip_refs_for_tasks(
            db, user_id=user.id, task_ids=[task.id]
        )
        assert refs[task.id][0] == clip.id
        assert refs[task.id][1] == "Pro C"
        assert refs[task.id][2] is True
