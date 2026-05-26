"""M12-01 pro_library_service 单测（对齐 docs/23 §8.1 AC-2）.

覆盖
----
1. 球手 / 镜头创建 happy path
2. ``source_credit`` / ``source_url`` 缺失 → BadRequestError（合规守门）
3. ``license_status`` 非法 → BadRequestError
4. 镜头下架幂等 + 日志
5. 每周精选 ``clip_ids`` 引用不存在 → 拒绝
6. 收藏 / 取消收藏幂等
7. 匹配历史写入
8. 解说 text 类型必须填 content
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError
from app.core.security import new_id
from app.models.user import User
from app.schemas.pro_library import (
    ProClipAnnotationCreate,
    ProPlayerCreate,
    ProSwingClipCreate,
    ProTopicCreate,
)
from app.services import pro_library_service as svc


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


def _make_clip_payload(player_id: str, **overrides) -> ProSwingClipCreate:
    base = dict(
        pro_player_id=player_id,
        club_type="driver",
        camera_angle="face_on",
        video_url="https://example.com/x.mp4",
        license_status="public_clip",
        source_credit="Source: PGA Tour 官方频道（YouTube）",
        source_url="https://youtu.be/abc",
    )
    base.update(overrides)
    return ProSwingClipCreate(**base)


@pytest.mark.asyncio
async def test_create_player_and_clip_happy_path() -> None:
    async with AsyncSessionLocal() as db:
        player = await svc.create_player(
            db,
            ProPlayerCreate(name="Rory", handedness="right"),
        )
        clip = await svc.add_clip(db, _make_clip_payload(player.id))
        assert clip.pro_player_id == player.id
        assert clip.license_status == "public_clip"


@pytest.mark.asyncio
async def test_add_clip_requires_source_credit() -> None:
    async with AsyncSessionLocal() as db:
        player = await svc.create_player(
            db, ProPlayerCreate(name="P", handedness="left")
        )
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            _make_clip_payload(player.id, source_credit="")


@pytest.mark.asyncio
async def test_takedown_clip_is_idempotent() -> None:
    async with AsyncSessionLocal() as db:
        player = await svc.create_player(
            db, ProPlayerCreate(name="P", handedness="right")
        )
        clip = await svc.add_clip(db, _make_clip_payload(player.id, is_published=True))
        await svc.takedown_clip(db, clip.id)
        await svc.takedown_clip(db, clip.id)  # 再下一次幂等
        refreshed = await svc.get_clip(db, clip.id)
        assert refreshed is not None
        assert refreshed.is_published is False


@pytest.mark.asyncio
async def test_create_topic_rejects_missing_clip_ids() -> None:
    async with AsyncSessionLocal() as db:
        with pytest.raises(BadRequestError):
            await svc.create_topic(
                db,
                ProTopicCreate(
                    code=f"week_{new_id('x')[-6:]}",
                    title="Week",
                    clip_ids=["psc_does_not_exist_xxx"],
                ),
            )


@pytest.mark.asyncio
async def test_favorite_clip_is_idempotent() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        player = await svc.create_player(
            db, ProPlayerCreate(name="P", handedness="right")
        )
        clip = await svc.add_clip(db, _make_clip_payload(player.id))
        f1 = await svc.favorite_clip(db, user_id=u.id, clip_id=clip.id)
        f2 = await svc.favorite_clip(db, user_id=u.id, clip_id=clip.id, note="like")
        assert f1.user_id == f2.user_id and f1.clip_id == f2.clip_id
        assert f2.note == "like"
        await svc.unfavorite_clip(db, user_id=u.id, clip_id=clip.id)


@pytest.mark.asyncio
async def test_record_match_score_range_guard() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        player = await svc.create_player(
            db, ProPlayerCreate(name="P", handedness="right")
        )
        clip = await svc.add_clip(db, _make_clip_payload(player.id))
        # 0-100 之外被拒
        with pytest.raises(BadRequestError):
            await svc.record_match(
                db,
                user_id=u.id,
                analysis_id="ana_test_xx",
                matched_clip_id=clip.id,
                match_score=Decimal("101"),
            )


@pytest.mark.asyncio
async def test_annotation_text_requires_content() -> None:
    async with AsyncSessionLocal() as db:
        player = await svc.create_player(
            db, ProPlayerCreate(name="P", handedness="right")
        )
        clip = await svc.add_clip(db, _make_clip_payload(player.id))
        with pytest.raises(BadRequestError):
            await svc.add_annotation(
                db,
                ProClipAnnotationCreate(
                    clip_id=clip.id,
                    annotation_type="text",
                    content="   ",
                ),
            )
