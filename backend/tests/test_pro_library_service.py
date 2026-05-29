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

from datetime import date
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
async def test_get_current_published_topic_prefers_latest_week(
) -> None:
    async with AsyncSessionLocal() as db:
        player = await svc.create_player(
            db, ProPlayerCreate(name="P", handedness="right")
        )
        clip = await svc.add_clip(
            db,
            _make_clip_payload(player.id, is_published=True),
        )
        older = await svc.create_topic(
            db,
            ProTopicCreate(
                code=f"week_old_{new_id('x')[-6:]}",
                title="Old",
                clip_ids=[clip.id],
                week_starts_at=date(2026, 1, 1),
                is_published=True,
            ),
        )
        newer = await svc.create_topic(
            db,
            ProTopicCreate(
                code=f"week_new_{new_id('x')[-6:]}",
                title="New",
                clip_ids=[clip.id],
                week_starts_at=date(2026, 5, 1),
                is_published=True,
            ),
        )
        await db.commit()

        current = await svc.get_current_published_topic(db)
        assert current is not None
        assert current.id == newer.id
        assert current.id != older.id


@pytest.mark.asyncio
async def test_seed_initial_weekly_topic_is_idempotent() -> None:
    async with AsyncSessionLocal() as db:
        await svc.seed_initial_pros(db)
        first = await svc.seed_initial_weekly_topic(db)
        second = await svc.seed_initial_weekly_topic(db)
        await db.commit()
        assert first is not None
        assert second is not None
        assert first.id == second.id


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


# ============================ M12-02 域名白名单 + 列表 + seed ============================


def test_is_video_url_allowed_pure() -> None:
    """_is_video_url_allowed 纯函数：默认白名单 + 子域名不传染 + 协议过滤."""

    # 默认白名单内
    assert svc._is_video_url_allowed("https://example.com/x.mp4") is True
    assert svc._is_video_url_allowed("https://minio.local/y.mp4") is True
    # 端口号不影响匹配
    assert svc._is_video_url_allowed("https://example.com:9000/x.mp4") is True
    # 子域名不传染（cdn.example.com 不在白名单 → False）
    assert svc._is_video_url_allowed("https://cdn.example.com/x.mp4") is False
    # 协议必须是 http/https
    assert svc._is_video_url_allowed("file:///etc/passwd") is False
    assert svc._is_video_url_allowed("ftp://example.com/x.mp4") is False
    # 空 / 非法
    assert svc._is_video_url_allowed("") is False
    assert svc._is_video_url_allowed("not a url") is False


@pytest.mark.asyncio
async def test_add_clip_rejects_video_url_outside_whitelist() -> None:
    """video_url 域名不在白名单 → 40040，不写入任何数据."""

    async with AsyncSessionLocal() as db:
        player = await svc.create_player(
            db, ProPlayerCreate(name="WhitelistTest", handedness="right")
        )
        bad = _make_clip_payload(
            player.id,
            video_url="https://evil.malicious-pirate-site.com/leaked.mp4",
        )
        with pytest.raises(BadRequestError) as exc_info:
            await svc.add_clip(db, bad)
        assert exc_info.value.code == 40040


@pytest.mark.asyncio
async def test_add_clip_rejects_thumbnail_outside_whitelist() -> None:
    """thumbnail_url 同样守门，但 None 时跳过."""

    async with AsyncSessionLocal() as db:
        player = await svc.create_player(
            db, ProPlayerCreate(name="ThumbTest", handedness="right")
        )
        # video_url 合法 + thumbnail_url 非法
        bad = _make_clip_payload(
            player.id,
            video_url="https://example.com/ok.mp4",
            thumbnail_url="https://random-image-host.com/leaked.jpg",
        )
        with pytest.raises(BadRequestError) as exc_info:
            await svc.add_clip(db, bad)
        assert exc_info.value.code == 40040

        # thumbnail=None 合法（仅 video_url 检查通过）
        ok_payload = _make_clip_payload(
            player.id,
            video_url="https://example.com/ok.mp4",
            thumbnail_url=None,
        )
        clip = await svc.add_clip(db, ok_payload)
        assert clip.thumbnail_url is None


@pytest.mark.asyncio
async def test_add_clip_accepts_custom_domain_whitelist() -> None:
    """allowed_video_domains 参数可注入新域名（运营加 CDN 域时的钩子）."""

    async with AsyncSessionLocal() as db:
        player = await svc.create_player(
            db, ProPlayerCreate(name="CustomDomain", handedness="right")
        )
        custom_domains = frozenset({"custom-cdn.example.org"})
        payload = _make_clip_payload(
            player.id,
            video_url="https://custom-cdn.example.org/x.mp4",
        )
        clip = await svc.add_clip(
            db, payload, allowed_video_domains=custom_domains
        )
        assert clip.video_url == "https://custom-cdn.example.org/x.mp4"


@pytest.mark.asyncio
async def test_list_active_players_excludes_soft_deleted() -> None:
    """list_active_players 不返回 is_active=False 球手."""

    async with AsyncSessionLocal() as db:
        active = await svc.create_player(
            db, ProPlayerCreate(name="ActivePro", handedness="right", sort_order=10)
        )
        inactive = await svc.create_player(
            db,
            ProPlayerCreate(
                name="InactivePro",
                handedness="right",
                is_active=False,
                sort_order=20,
            ),
        )
        players = await svc.list_active_players(db)
        ids = {p.id for p in players}
        assert active.id in ids
        assert inactive.id not in ids


@pytest.mark.asyncio
async def test_seed_initial_pros_is_idempotent() -> None:
    """seed_initial_pros 连续两次 → 同一 player + 同一 clip，不重复."""

    async with AsyncSessionLocal() as db:
        first = await svc.seed_initial_pros(db)
        second = await svc.seed_initial_pros(db)

        assert len(first) == 1
        assert len(second) == 1
        assert first[0].id == second[0].id
        assert first[0].name == "Demo Pro · 内置示例"
        clips = await svc.list_published_clips(db, player_id=first[0].id)
        assert len(clips) == 1
        assert clips[0].is_published is True
        evo = (clips[0].features_snapshot or {}).get("evolution_poses")
        assert evo
        assert "early_extension" in evo
        assert "chicken_wing" in evo
        assert "reverse_spine" in evo
