"""二期 M12 球手对比库服务（对齐 docs/23 §8.1）.

职责
----
- pro_players / pro_swing_clips / pro_topics CRUD + 发布闸门
- 收藏 / 取消收藏（幂等）
- 匹配历史 ``user_pro_match_history`` 写入
- ``license_status`` / ``source_credit`` 合规守门

本 PR 边界
---------
- 匹配算法在 ``pro_match_service``（M12-04）；``GET /v1/analyses/{id}/pro-matches`` 路由
- 读端点在 ``/v1/pros``（M12-02）；写端点 / 收藏按需后续 PR
- **不**做版权采集后台（长期议题）
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from urllib.parse import urlparse

from sqlalchemy import delete, or_, select
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


def _stick_pose(
    *,
    hip_x: float = 0.5,
    l_shoulder_y: float = 0.25,
    r_shoulder_y: float = 0.25,
    l_elbow_x: float = 0.38,
    l_wrist_x: float = 0.35,
) -> list[dict[str, float]]:
    """M12-08 简化 9 点 stick figure（归一化坐标）."""

    return [
        {"x": 0.5, "y": 0.15},
        {"x": 0.5, "y": 0.22},
        {"x": 0.42, "y": l_shoulder_y},
        {"x": 0.58, "y": r_shoulder_y},
        {"x": l_elbow_x, "y": 0.38},
        {"x": 0.62, "y": 0.38},
        {"x": l_wrist_x, "y": 0.52},
        {"x": 0.65, "y": 0.52},
        {"x": hip_x, "y": 0.42},
    ]


DEMO_EVOLUTION_POSES: dict[str, dict] = {
    "early_extension": {
        "label": "早伸修复示意",
        "user": _stick_pose(hip_x=0.56),
        "pro": _stick_pose(hip_x=0.48),
    },
    "chicken_wing": {
        "label": "鸡翼肘改善示意",
        "user": _stick_pose(l_elbow_x=0.46, l_wrist_x=0.44),
        "pro": _stick_pose(l_elbow_x=0.36, l_wrist_x=0.34),
    },
    "reverse_spine": {
        "label": "脊柱回正示意",
        "user": _stick_pose(l_shoulder_y=0.28, r_shoulder_y=0.22),
        "pro": _stick_pose(l_shoulder_y=0.25, r_shoulder_y=0.25),
    },
}


async def _ensure_demo_clip_evolution_poses(
    db: AsyncSession, player: ProPlayer
) -> None:
    """幂等：demo clip 写入 M12-08 evolution_poses stub."""

    row = await db.execute(
        select(ProSwingClip)
        .where(
            ProSwingClip.pro_player_id == player.id,
            ProSwingClip.is_published.is_(True),
        )
        .limit(1)
    )
    clip = row.scalar_one_or_none()
    if clip is None:
        return
    snap = dict(clip.features_snapshot or {})
    if snap.get("evolution_poses"):
        return
    snap["evolution_poses"] = DEMO_EVOLUTION_POSES
    clip.features_snapshot = snap
    await db.flush()
    logger.info("seed_pro_evolution_poses_done", clip_id=clip.id)


# 球手镜头 video_url 允许的域名白名单（合规 + 安全）。
# 设计考量
# --------
# - 球手镜头一律是版权敏感内容，**禁止** 直链第三方未授权的视频站；只允许：
#   * 自有对象存储 cdn 域名
#   * mock / dev 占位域名
# - 上线前运营把真实 CDN 域名加入 ``PRO_CLIP_ALLOWED_VIDEO_DOMAINS`` 即可，
#   不需要改代码。生产 deployment 时由 ``settings`` 注入扩充。
# - 测试 / fixture 用 example.com / minio.local，已包含。
DEFAULT_PRO_CLIP_DOMAINS: frozenset[str] = frozenset(
    {
        # 测试 / mock
        "example.com",
        "minio.local",
        # 自有对象存储常见前缀
        "cos.ap-shanghai.myqcloud.com",
        "cdn.lingniao-golf.com",
    }
)


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


async def list_active_players(db: AsyncSession) -> list[ProPlayer]:
    """供 M12-03 资源库 tab UI 拉取球手列表（按 sort_order 升序）.

    不展露 ``is_active=False`` 的球手：版权下架或合作终止后用 ``is_active=False``
    软隔离，列表不再可见，但已有的收藏 / 匹配历史不破坏。
    """

    rows = await db.execute(
        select(ProPlayer)
        .where(ProPlayer.is_active.is_(True))
        .order_by(ProPlayer.sort_order.asc(), ProPlayer.name.asc())
    )
    return list(rows.scalars().all())


# ---------------- 镜头 ----------------


def _is_video_url_allowed(
    url: str, allowed_domains: frozenset[str] | None = None
) -> bool:
    """检查 video_url 域名是否在 allowed_domains 内.

    设计
    ----
    - 用 ``urlparse`` 解析 ``netloc`` 取主机名；不接受 IP 字面量（生产场景几乎都是
      CDN 域名）
    - 允许端口号（``example.com:9000`` 仍 match ``example.com``）
    - 子域名不传染：``cdn.example.com`` 不会因为 ``example.com`` 在白名单就通过；
      因为后者只允许那个具体域，避免子域名"泛白名单"被滥用
    """

    allowed = allowed_domains or DEFAULT_PRO_CLIP_DOMAINS
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname or ""
    return host in allowed


async def add_clip(
    db: AsyncSession,
    payload: ProSwingClipCreate,
    *,
    allowed_video_domains: frozenset[str] | None = None,
) -> ProSwingClip:
    """入库一条球手镜头，强制 source_credit + license_status + 域名白名单合规.

    M12-02 加固
    -----------
    - ``video_url`` 必须在 ``allowed_video_domains``（默认 ``DEFAULT_PRO_CLIP_DOMAINS``）
      → 错 ``40040``。避免误入未授权的第三方视频站，被版权方一锅端。
      （不复用 40013：已被 payment_service.PaymentNotAllowedError 占用。）
    - ``thumbnail_url`` 同域名校验（None 时跳过）。
    """

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

    # 域名白名单校验（M12-02 加固）
    if not _is_video_url_allowed(payload.video_url, allowed_video_domains):
        raise BadRequestError(
            code=40040,
            message="video_url 域名不在白名单",
            detail=f"host={urlparse(payload.video_url).hostname}",
        )
    if payload.thumbnail_url and not _is_video_url_allowed(
        payload.thumbnail_url, allowed_video_domains
    ):
        raise BadRequestError(
            code=40040,
            message="thumbnail_url 域名不在白名单",
            detail=f"host={urlparse(payload.thumbnail_url).hostname}",
        )

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


async def get_current_published_topic(db: AsyncSession) -> ProTopic | None:
    """返回当前生效的每周精选（``is_published`` + ``week_starts_at`` 已到期）."""

    today = date.today()
    row = await db.execute(
        select(ProTopic)
        .where(
            ProTopic.is_published.is_(True),
            or_(ProTopic.week_starts_at.is_(None), ProTopic.week_starts_at <= today),
        )
        .order_by(
            ProTopic.week_starts_at.desc().nulls_last(),
            ProTopic.published_at.desc().nulls_last(),
            ProTopic.created_at.desc(),
        )
        .limit(1)
    )
    return row.scalar_one_or_none()


async def load_topic_clip_items(
    db: AsyncSession, topic: ProTopic
) -> list[tuple[ProSwingClip, ProPlayer]]:
    """按 ``clip_ids`` 顺序返回已发布镜头 + 在架球手；缺失 id 静默跳过."""

    if not topic.clip_ids:
        return []
    rows = await db.execute(
        select(ProSwingClip, ProPlayer)
        .join(ProPlayer, ProPlayer.id == ProSwingClip.pro_player_id)
        .where(
            ProSwingClip.id.in_(list(topic.clip_ids)),
            ProSwingClip.is_published.is_(True),
            ProPlayer.is_active.is_(True),
        )
    )
    by_id = {clip.id: (clip, player) for clip, player in rows.all()}
    return [by_id[cid] for cid in topic.clip_ids if cid in by_id]


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


async def seed_initial_pros(db: AsyncSession) -> list[ProPlayer]:
    """开发 / E2E 用：写入 1 个 demo 球手 + 1 条 published clip，幂等.

    设计要点
    --------
    - **幂等**：用 ``pro_players.name`` 简单判重（mock 数据，name 唯一即可）
    - ``license_status=public_clip``：所有内置 demo 数据声明为公开镜头，配 ``source_credit``
      标注 "internal demo"，避免误认为外部版权来源
    - ``video_url`` 用 ``minio.local`` 测试占位，落在 ``DEFAULT_PRO_CLIP_DOMAINS`` 白名单内
    """

    name = "Demo Pro · 内置示例"
    existing = await db.execute(select(ProPlayer).where(ProPlayer.name == name))
    player = existing.scalar_one_or_none()
    if player is not None:
        await _ensure_demo_clip_evolution_poses(db, player)
        return [player]

    player = ProPlayer(
        id=new_id("pp"),
        name=name,
        name_en="Demo Pro",
        nationality="CHN",
        handedness="right",
        height_cm=180,
        avatar_url=None,
        short_bio="内置示例球手，用于 M12 资源库联调；上线时由真实球手替换。",
        license_status="public_clip",
        is_active=True,
        sort_order=0,
    )
    db.add(player)
    await db.flush()

    clip = ProSwingClip(
        id=new_id("psc"),
        pro_player_id=player.id,
        club_type="iron_7",
        camera_angle="face_on",
        video_url="https://minio.local/demo/pro_iron7_face_on.mp4",
        thumbnail_url="https://minio.local/demo/pro_iron7_thumb.jpg",
        duration_ms=4500,
        fps=60,
        overall_score=92,
        engine_version="v1",
        features_snapshot={
            "shoulder_turn_deg": 92,
            "tempo_ratio": 3.1,
            "evolution_poses": DEMO_EVOLUTION_POSES,
        },
        phase_timestamps={"address": 0, "top": 1200, "impact": 2200},
        license_status="public_clip",
        source_credit="Birdie Golf · internal demo (M12-02 seed)",
        source_url="https://minio.local/demo/source_metadata.txt",
        captured_year=2026,
        description="示例：标准 7 号铁 face-on 镜头；用于资源库 / 对比联调",
        is_published=True,
    )
    db.add(clip)
    await db.flush()
    logger.info(
        "seed_initial_pros_done", player_id=player.id, clip_id=clip.id
    )
    return [player]


async def seed_initial_weekly_topic(db: AsyncSession) -> ProTopic | None:
    """开发 / E2E：幂等写入 1 条 published 每周精选，引用 demo clip."""

    code = "demo_weekly_m12"
    existing = await db.execute(select(ProTopic).where(ProTopic.code == code))
    topic = existing.scalar_one_or_none()
    if topic is not None:
        return topic

    await seed_initial_pros(db)
    clip_row = await db.execute(
        select(ProSwingClip)
        .join(ProPlayer, ProPlayer.id == ProSwingClip.pro_player_id)
        .where(
            ProPlayer.name == "Demo Pro · 内置示例",
            ProSwingClip.is_published.is_(True),
        )
        .limit(1)
    )
    clip = clip_row.scalar_one_or_none()
    if clip is None:
        return None

    topic = await create_topic(
        db,
        ProTopicCreate(
            code=code,
            title="本周精选 · 7 号铁正面示范",
            subtitle="跟 Demo Pro 学标准 timing",
            summary="内置示例专题，用于 M12-06 每周精选 banner 与镜头列表联调。",
            clip_ids=[clip.id],
            week_starts_at=date.today(),
            is_published=True,
        ),
    )
    topic.published_at = datetime.now(UTC)
    await db.flush()
    logger.info("seed_initial_weekly_topic_done", topic_id=topic.id, clip_id=clip.id)
    return topic


__all__ = [
    "DEFAULT_PRO_CLIP_DOMAINS",
    "add_annotation",
    "add_clip",
    "create_player",
    "create_topic",
    "favorite_clip",
    "get_clip",
    "get_current_published_topic",
    "get_player",
    "list_active_players",
    "list_published_clips",
    "load_topic_clip_items",
    "record_match",
    "seed_initial_pros",
    "seed_initial_weekly_topic",
    "takedown_clip",
    "unfavorite_clip",
]
