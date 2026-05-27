"""二期 M9 画像 2.0 服务（对齐 docs/23 §5.1）.

职责
----
- ``UserProfileV2`` upsert：一对一表，缺则建、有则补字段
- ``user_clubs`` CRUD：单用户最多 14 支（``MAX_CLUBS_PER_USER``）
- **字段级 consent 投影**：读时按 ``privacy_payload`` 把对应字段清空；写时
  ``consent=False`` 强制清空该组字段（保留删除权）

约束兜底
-------
- DB 层：``CheckConstraint`` 校验数值范围 / 枚举 / 利手
- 服务层：14 支上限、consent 强一致性、``known_injuries`` 透传 LLM 拦截

灰度
----
- 配置 ``PHASE2_PROFILE_V2_ENABLED=False`` 时，调用方应在路由层直接 ``404``，
  本模块不做 flag 短路，避免后续单测和路由两边都写一次
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.meetup import Venue
from app.models.user_profile_v2 import (
    COACH_VISIBLE_ALLOWED,
    CONSENT_FIELDS,
    MAX_CLUBS_PER_USER,
    MAX_FAVORITE_VENUES,
    UserClub,
    UserProfileV2,
)
from app.schemas.user_profile_v2 import (
    UserClubCreate,
    UserClubUpdate,
    UserProfileV2Update,
)

logger = get_logger("user_profile_v2")

# consent 字段 → 受其控制的列名集合
_CONSENT_TO_COLUMNS: dict[str, tuple[str, ...]] = {
    "handicap_consent": ("handicap_official", "handicap_self", "handicap_source"),
    "body_consent": ("height_cm", "weight_kg"),
    "injury_consent": ("known_injuries",),
    "location_consent": ("favorite_course_ids",),
    "coach_visible_consent": ("coach_visible_fields",),
}

# 写入时这些列允许 client 显式传 None / 空列表（不视为"未提供"）
_SETTABLE_COLUMNS: frozenset[str] = frozenset(
    {
        "handicap_official",
        "handicap_self",
        "handicap_source",
        "height_cm",
        "weight_kg",
        "handedness",
        "known_injuries",
        "mid_long_goals",
        "training_preference",
        "training_preference_meta",
        "weekly_target_sessions",
        "favorite_course_ids",
        "coach_visible_fields",
    }
)

# 视为"清空"的默认值（JSONB 列）
_EMPTY_LIST_COLUMNS: frozenset[str] = frozenset(
    {"known_injuries", "favorite_course_ids", "coach_visible_fields"}
)


def _empty_value(column: str):
    if column in _EMPTY_LIST_COLUMNS:
        return []
    return None


async def get_profile(db: AsyncSession, user_id: str) -> UserProfileV2 | None:
    """返回原始 ORM 行，**不做** consent 投影；presenter 自行处理。"""

    row = await db.execute(
        select(UserProfileV2).where(UserProfileV2.user_id == user_id)
    )
    return row.scalar_one_or_none()


async def upsert_profile(
    db: AsyncSession,
    *,
    user_id: str,
    payload: UserProfileV2Update,
) -> UserProfileV2:
    """按 patch 语义更新 ``user_profiles_v2``，必要时插入.

    consent 处理：
    - 调用方可同时传字段值与 ``privacy_payload``
    - 服务层会在 patch 阶段保留两者的"最终态"，再校验"任何 consent=False 的字段
      都被清空"，否则抛 ``BadRequestError``
    """

    existing = await get_profile(db, user_id)
    is_new = existing is None
    profile = existing or UserProfileV2(user_id=user_id, privacy_payload={})

    # 1) coach_visible_fields 白名单校验
    if payload.coach_visible_fields is not None:
        _validate_coach_visible_fields(payload.coach_visible_fields)

    # 1.5) favorite_course_ids 存在性 + 上限校验（M9-05）
    # schema 已校验 max_length；这里只校验「ID 必须真实存在于 venues 且 status='active'」。
    # 注意：列表去重（保持顺序，去掉后位重复，避免「6 个里 3 个重复」的视觉欺骗）。
    if payload.favorite_course_ids is not None:
        deduped = _dedupe_preserve_order(payload.favorite_course_ids)
        if len(deduped) > MAX_FAVORITE_VENUES:
            # 理论上 schema 已拦截；保险起见在 dedupe 后再 check 一次。
            # 40020 段：M9 画像扩展业务码（40020-40029）。
            # 不复用 40003（已被 analysis_service 占用为"视频格式不支持"）。
            raise BadRequestError(
                code=40020,
                message="favorite_course_ids 超出上限",
                detail=f"最多 {MAX_FAVORITE_VENUES} 个，去重后实际 {len(deduped)}",
            )
        if deduped:
            await _validate_favorite_venue_ids(db, deduped)
        # 把 dedupe 后的列表回写到 payload，避免后续 _SETTABLE_COLUMNS 应用时重复
        payload = payload.model_copy(update={"favorite_course_ids": deduped})

    # 2) 计算"最终态"的 privacy payload（旧 payload merge 新 patch）
    next_payload: dict[str, bool] = dict(profile.privacy_payload or {})
    if payload.privacy_payload is not None:
        next_payload.update(payload.privacy_payload.model_dump())
    # 缺省字段当作 False，避免遗漏 consent 校验
    for key in CONSENT_FIELDS:
        next_payload.setdefault(key, False)

    # 3) 应用字段 patch（仅显式提供的列）
    explicit = payload.model_dump(exclude_unset=True)
    explicit.pop("privacy_payload", None)
    for column, value in explicit.items():
        if column in _SETTABLE_COLUMNS:
            setattr(profile, column, value)

    # 4) consent=False → 强制清空对应列（保留删除权）
    for consent_key, columns in _CONSENT_TO_COLUMNS.items():
        if not next_payload.get(consent_key, False):
            for column in columns:
                setattr(profile, column, _empty_value(column))

    profile.privacy_payload = next_payload

    if is_new:
        db.add(profile)
    await db.flush()

    logger.info(
        "user_profile_v2_upserted",
        user_id=user_id,
        is_new=is_new,
        consent_keys=[k for k, v in next_payload.items() if v],
    )
    return profile


def _validate_coach_visible_fields(fields: list[str]) -> None:
    if not fields:
        return
    bad = [f for f in fields if f not in COACH_VISIBLE_ALLOWED]
    if bad:
        raise BadRequestError(
            code=40001,
            message="coach_visible_fields 含非法字段",
            detail=f"不允许的字段：{','.join(bad)}",
        )


def project_for_self(profile: UserProfileV2) -> dict:
    """按 ``privacy_payload`` 投影，给"用户自己"看的完整视图.

    对**自己**而言，所有字段都可见（consent 控制的是"是否可对外/教练曝光"），
    所以这里直接把全字段平摊成 dict。
    """

    return {
        "user_id": profile.user_id,
        "handicap_official": profile.handicap_official,
        "handicap_self": profile.handicap_self,
        "handicap_source": profile.handicap_source,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "handedness": profile.handedness,
        "known_injuries": list(profile.known_injuries or []),
        "mid_long_goals": list(profile.mid_long_goals or []),
        "training_preference": profile.training_preference,
        "training_preference_meta": (
            dict(profile.training_preference_meta)
            if profile.training_preference_meta
            else None
        ),
        "weekly_target_sessions": profile.weekly_target_sessions,
        "favorite_course_ids": list(profile.favorite_course_ids or []),
        "privacy_payload": dict(profile.privacy_payload or {}),
        "coach_visible_fields": list(profile.coach_visible_fields or []),
    }


def project_for_coach(profile: UserProfileV2) -> dict:
    """给"教练"看的字段子集（M9-06 配合 ``coach_visible_consent``）."""

    payload = profile.privacy_payload or {}
    if not payload.get("coach_visible_consent", False):
        return {"user_id": profile.user_id}

    visible: set[str] = set(profile.coach_visible_fields or [])
    base = project_for_self(profile)
    return {
        "user_id": profile.user_id,
        **{k: v for k, v in base.items() if k in visible},
    }


def llm_prompt_safe_context(profile: UserProfileV2) -> dict:
    """供 LLM prompt 拼接用，**强制**剔除高敏感字段（docs/06 §13.1）.

    - 永远剔除 ``known_injuries``、``height_cm``、``weight_kg``
    - 其余字段按 ``privacy_payload`` 投影
    """

    payload = profile.privacy_payload or {}
    out: dict = {"user_id": profile.user_id}
    if payload.get("handicap_consent"):
        out["handicap_self"] = (
            float(profile.handicap_self) if profile.handicap_self is not None else None
        )
        out["handicap_official"] = (
            float(profile.handicap_official) if profile.handicap_official is not None else None
        )
    if profile.training_preference:
        out["training_preference"] = profile.training_preference
    if profile.mid_long_goals:
        out["mid_long_goals"] = list(profile.mid_long_goals)
    # 利手不算高敏感；公开放行
    if profile.handedness:
        out["handedness"] = profile.handedness
    return out


# ------------------------------- 装备清单 -------------------------------


async def count_clubs(db: AsyncSession, user_id: str) -> int:
    row = await db.execute(
        select(func.count(UserClub.id)).where(UserClub.user_id == user_id)
    )
    return int(row.scalar_one() or 0)


async def list_clubs(db: AsyncSession, user_id: str) -> list[UserClub]:
    row = await db.execute(
        select(UserClub)
        .where(UserClub.user_id == user_id)
        .order_by(UserClub.sort_order.asc(), UserClub.created_at.asc())
    )
    return list(row.scalars().all())


async def add_club(
    db: AsyncSession, *, user_id: str, payload: UserClubCreate
) -> UserClub:
    """新增一支球杆，触发 14 支硬上限校验。"""

    current = await count_clubs(db, user_id)
    if current >= MAX_CLUBS_PER_USER:
        raise BadRequestError(
            code=40002,
            message=f"装备清单已达上限（{MAX_CLUBS_PER_USER} 支），请先删除再添加",
        )

    club = UserClub(
        id=new_id("ucb"),
        user_id=user_id,
        club_type=payload.club_type,
        nickname=payload.nickname,
        self_yardage_m=payload.self_yardage_m,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    db.add(club)
    await db.flush()
    logger.info(
        "user_club_added",
        club_id=club.id,
        user_id=user_id,
        club_type=club.club_type,
        total_after=current + 1,
    )
    return club


async def update_club(
    db: AsyncSession,
    *,
    user_id: str,
    club_id: str,
    payload: UserClubUpdate,
) -> UserClub:
    row = await db.execute(
        select(UserClub).where(UserClub.id == club_id, UserClub.user_id == user_id)
    )
    club = row.scalar_one_or_none()
    if club is None:
        raise NotFoundError(code=40404, message="球杆不存在")

    patch = payload.model_dump(exclude_unset=True)
    for key, value in patch.items():
        setattr(club, key, value)
    await db.flush()
    logger.info("user_club_updated", club_id=club.id, fields=list(patch.keys()))
    return club


async def delete_club(db: AsyncSession, *, user_id: str, club_id: str) -> None:
    result = await db.execute(
        delete(UserClub).where(UserClub.id == club_id, UserClub.user_id == user_id)
    )
    if result.rowcount == 0:
        raise NotFoundError(code=40404, message="球杆不存在")
    logger.info("user_club_deleted", club_id=club_id, user_id=user_id)


def active_club_types(clubs: Iterable[UserClub]) -> list[str]:
    """供 M7-05 球杆标尺 / M7-16 LLM 文案查询用户当前在用球杆类型集合。"""

    return sorted({c.club_type for c in clubs if c.is_active})


# ------------------------------- M9-05 常去球馆 -------------------------------


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    """JSONB 数组顺序代表用户排序意图，去重必须保位（先到先留）。"""

    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


async def _validate_favorite_venue_ids(db: AsyncSession, ids: list[str]) -> None:
    """校验 ids 中的 venue 都存在且 status='active'.

    设计说明
    --------
    - **不在 DB 层加 FK**：JSONB 数组上加 FK 维护成本高；venue 状态需要软删除
      （status='closed'），FK 反而会阻断 venue 软关闭。
    - 这里在 service 层做"存在 + 可用"两段校验，错误信息列出缺失的 ID 便于客户端
      回滚选择；不暴露其他用户未公开 venue 的额外信息（venues 当前全表都是公开的）。
    """

    row = await db.execute(
        select(Venue.id).where(Venue.id.in_(ids), Venue.status == "active")
    )
    existing = {r[0] for r in row.all()}
    missing = [vid for vid in ids if vid not in existing]
    if missing:
        # 截断显示，避免 422 detail 过长（客户端只看前几条足以排错）
        shown = ", ".join(missing[:5])
        more = f"…等 {len(missing)} 条" if len(missing) > 5 else ""
        # 40021 段：与 40020 同段，归 M9 画像扩展业务码。
        # 不复用 40004（已被 analysis_service 占用为"视频时长不符"）。
        raise BadRequestError(
            code=40021,
            message="favorite_course_ids 含未知 / 已关闭的球场",
            detail=f"不可用 ID：{shown}{more}",
        )


async def list_favorite_venues(
    db: AsyncSession, *, user_id: str
) -> tuple[list[Venue], list[str]]:
    """返回 (按 favorite_course_ids 顺序排序的 venue 行, missing_ids).

    考虑：
    - **顺序**：用户在 profile 里手动排序的 chip 顺序必须保留，所以这里取出后按
      原 ids 顺序重排，而不是用 DB 默认顺序。
    - **missing_ids**：venue 可能在收藏后被运营 closed / 软删，这种条目从 items
      移除并返回 missing_ids，让客户端弹「该球场已下架，是否移除」。
    - **consent**：路由层应已在 ``location_consent=False`` 时短路返回空列表，
      避免本服务被无 consent 调用；这里不再二次拦截以保持职责单一。
    """

    profile = await get_profile(db, user_id)
    if profile is None:
        return ([], [])
    ids: list[str] = list(profile.favorite_course_ids or [])
    if not ids:
        return ([], [])

    row = await db.execute(
        select(Venue).where(Venue.id.in_(ids), Venue.status == "active")
    )
    venues: list[Venue] = list(row.scalars().all())
    by_id: dict[str, Venue] = {v.id: v for v in venues}
    ordered: list[Venue] = [by_id[vid] for vid in ids if vid in by_id]
    missing: list[str] = [vid for vid in ids if vid not in by_id]
    return (ordered, missing)


__all__ = [
    "active_club_types",
    "add_club",
    "count_clubs",
    "delete_club",
    "get_profile",
    "list_clubs",
    "list_favorite_venues",
    "llm_prompt_safe_context",
    "project_for_coach",
    "project_for_self",
    "update_club",
    "upsert_profile",
]
