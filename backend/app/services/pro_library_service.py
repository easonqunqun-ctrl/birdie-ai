"""二期 M12 球手对比库服务（对齐 docs/23 §8.1）.

职责
----
- pro_players / pro_swing_clips / pro_topics CRUD + 发布闸门
- 收藏 / 取消收藏（幂等）
- 匹配历史 ``user_pro_match_history`` 写入
- ``license_status`` / ``source_credit`` 合规守门

本 PR 边界
---------
- **不**做匹配算法（M12-04 单独 PR 引入）
- **不**做路由（M12-03 引入 ``/v1/pros``）
- **不**做版权采集后台（长期议题）
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.pro_library import (
    VALID_LICENSE_STATUSES,
    ProClipAnnotation,
    ProPlayer,
    ProSwingClip,
    ProTopic,
    UserProFavorite,
    UserProMatchHistory,
)
from app.schemas.pro_library import (
    ProClipAnnotationCreate,
    ProPlayerCreate,
    ProSwingClipCreate,
    ProTopicCreate,
)

logger = get_logger("pro_library")


# ---------------- 球手 ----------------


async def create_player(
    db: AsyncSession, payload: ProPlayerCreate
) -> ProPlayer:
    if payload.license_status not in VALID_LICENSE_STATUSES:
        raise BadRequestError(code=40001, message="license_status 非法")
    player = ProPlayer(
        id=new_id("pp"),
        name=payload.name,
        name_en=payload.name_en,
        nationality=payload.nationality,
        handedness=payload.handedness,
        height_cm=payload.height_cm,
        avatar_url=payload.avatar_url,
        short_bio=payload.short_bio,
        license_status=payload.license_status,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    db.add(player)
    await db.flush()
    logger.info("pro_player_created", player_id=player.id)
    return player


async def get_player(db: AsyncSession, player_id: str) -> ProPlayer | None:
    row = await db.execute(select(ProPlayer).where(ProPlayer.id == player_id))
    return row.scalar_one_or_none()


# ---------------- 镜头 ----------------


async def add_clip(
    db: AsyncSession, payload: ProSwingClipCreate
) -> ProSwingClip:
    """入库一条球手镜头，强制 source_credit + license_status 合规。"""

    player = await get_player(db, payload.pro_player_id)
    if player is None:
        raise NotFoundError(code=40406, message="球手不存在")
    if not payload.source_credit.strip():
        raise BadRequestError(
            code=40012,
            message="source_credit 必填（M12 合规硬约束）",
        )
    if not payload.source_url.strip():
        raise BadRequestError(
            code=40012,
            message="source_url 必填（M12 合规硬约束）",
        )
    if payload.license_status not in VALID_LICENSE_STATUSES:
        raise BadRequestError(code=40001, message="license_status 非法")

    clip = ProSwingClip(
        id=new_id("psc"),
        pro_player_id=payload.pro_player_id,
        club_type=payload.club_type,
        camera_angle=payload.camera_angle,
        video_url=payload.video_url,
        thumbnail_url=payload.thumbnail_url,
        duration_ms=payload.duration_ms,
        fps=payload.fps,
        overall_score=payload.overall_score,
        engine_version=payload.engine_version,
        features_snapshot=dict(payload.features_snapshot or {}),
        phase_timestamps=payload.phase_timestamps,
        license_status=payload.license_status,
        source_credit=payload.source_credit,
        source_url=payload.source_url,
        captured_year=payload.captured_year,
        description=payload.description,
        is_published=payload.is_published,
    )
    db.add(clip)
    await db.flush()
    logger.info(
        "pro_clip_added",
        clip_id=clip.id,
        player_id=clip.pro_player_id,
        license=clip.license_status,
    )
    return clip


async def list_published_clips(
    db: AsyncSession, *, player_id: str | None = None, club_type: str | None = None
) -> list[ProSwingClip]:
    stmt = select(ProSwingClip).where(ProSwingClip.is_published.is_(True))
    if player_id:
        stmt = stmt.where(ProSwingClip.pro_player_id == player_id)
    if club_type:
        stmt = stmt.where(ProSwingClip.club_type == club_type)
    rows = await db.execute(stmt.order_by(ProSwingClip.created_at.desc()))
    return list(rows.scalars().all())


async def get_clip(db: AsyncSession, clip_id: str) -> ProSwingClip | None:
    row = await db.execute(select(ProSwingClip).where(ProSwingClip.id == clip_id))
    return row.scalar_one_or_none()


async def takedown_clip(db: AsyncSession, clip_id: str) -> ProSwingClip:
    """收到版权投诉时的 24h 内下架（``is_published=False``）。"""

    clip = await get_clip(db, clip_id)
    if clip is None:
        raise NotFoundError(code=40406, message="镜头不存在")
    if not clip.is_published:
        return clip
    clip.is_published = False
    await db.flush()
    logger.warning(
        "pro_clip_takedown",
        clip_id=clip_id,
        player_id=clip.pro_player_id,
        reason="copyright_or_takedown_request",
    )
    return clip


# ---------------- PGC 解说 ----------------


async def add_annotation(
    db: AsyncSession, payload: ProClipAnnotationCreate
) -> ProClipAnnotation:
    clip = await get_clip(db, payload.clip_id)
    if clip is None:
        raise NotFoundError(code=40406, message="镜头不存在")
    if payload.annotation_type == "text" and not (payload.content or "").strip():
        raise BadRequestError(code=40001, message="text 解说必须填 content")

    ann = ProClipAnnotation(
        id=new_id("pca"),
        clip_id=payload.clip_id,
        author_user_id=payload.author_user_id,
        annotation_type=payload.annotation_type,
        content=payload.content,
        time_marker_ms=payload.time_marker_ms,
        is_visible=payload.is_visible,
    )
    db.add(ann)
    await db.flush()
    return ann


# ---------------- 每周精选 ----------------


async def create_topic(db: AsyncSession, payload: ProTopicCreate) -> ProTopic:
    if payload.clip_ids:
        rows = await db.execute(
            select(ProSwingClip.id).where(ProSwingClip.id.in_(list(payload.clip_ids)))
        )
        found = {r[0] for r in rows.all()}
        missing = set(payload.clip_ids) - found
        if missing:
            raise BadRequestError(
                code=40010,
                message="pro_topic 引用的 clip 不存在",
                detail=f"缺失：{','.join(sorted(missing))}",
            )
    topic = ProTopic(
        id=new_id("pt"),
        code=payload.code,
        title=payload.title,
        subtitle=payload.subtitle,
        banner_url=payload.banner_url,
        summary=payload.summary,
        clip_ids=list(payload.clip_ids),
        week_starts_at=payload.week_starts_at,
        is_published=payload.is_published,
    )
    db.add(topic)
    await db.flush()
    return topic


# ---------------- 收藏 ----------------


async def favorite_clip(
    db: AsyncSession, *, user_id: str, clip_id: str, note: str | None = None
) -> UserProFavorite:
    clip = await get_clip(db, clip_id)
    if clip is None:
        raise NotFoundError(code=40406, message="镜头不存在")
    row = await db.execute(
        select(UserProFavorite).where(
            UserProFavorite.user_id == user_id, UserProFavorite.clip_id == clip_id
        )
    )
    existing = row.scalar_one_or_none()
    if existing is not None:
        if note is not None:
            existing.note = note
            await db.flush()
        return existing
    fav = UserProFavorite(user_id=user_id, clip_id=clip_id, note=note)
    db.add(fav)
    await db.flush()
    return fav


async def unfavorite_clip(db: AsyncSession, *, user_id: str, clip_id: str) -> None:
    await db.execute(
        delete(UserProFavorite).where(
            UserProFavorite.user_id == user_id, UserProFavorite.clip_id == clip_id
        )
    )


# ---------------- 匹配历史 ----------------


async def record_match(
    db: AsyncSession,
    *,
    user_id: str,
    analysis_id: str,
    matched_clip_id: str,
    match_score: Decimal,
    match_details: dict | None = None,
) -> UserProMatchHistory:
    if not (Decimal("0") <= match_score <= Decimal("100")):
        raise BadRequestError(code=40001, message="match_score 必须在 0-100")
    clip = await get_clip(db, matched_clip_id)
    if clip is None:
        raise NotFoundError(code=40406, message="镜头不存在")
    rec = UserProMatchHistory(
        id=new_id("upmh"),
        user_id=user_id,
        analysis_id=analysis_id,
        matched_clip_id=matched_clip_id,
        match_score=match_score,
        match_details=dict(match_details or {}),
    )
    db.add(rec)
    await db.flush()
    logger.info(
        "match_recorded",
        user_id=user_id,
        analysis_id=analysis_id,
        clip_id=matched_clip_id,
        score=str(match_score),
    )
    return rec


__all__ = [
    "add_annotation",
    "add_clip",
    "create_player",
    "create_topic",
    "favorite_clip",
    "get_clip",
    "get_player",
    "list_published_clips",
    "record_match",
    "takedown_clip",
    "unfavorite_clip",
]
