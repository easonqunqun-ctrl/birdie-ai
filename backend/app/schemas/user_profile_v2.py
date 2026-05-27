"""二期 M9 画像 2.0 Pydantic schema（对齐 docs/23 §5.1）.

读 / 写两套 schema：写时所有字段可选（patch 语义），读时返回字段级 consent 投影后
的结果（consent=false 的字段直接 ``None``，详 ``user_profile_v2_service``）。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.user_profile_v2 import MAX_FAVORITE_VENUES

HandednessLiteral = Literal["right", "left", "switch"]
HandicapSourceLiteral = Literal["rcga", "usga", "self"]
TrainingPreferenceLiteral = Literal["video", "text", "mixed"]
ClubTypeLiteral = Literal[
    "driver",
    "wood",
    "hybrid",
    "iron",
    "wedge",
    "putter",
]


class PrivacyPayload(BaseModel):
    """字段级同意位载荷（FR-3）."""

    handicap_consent: bool = False
    body_consent: bool = False
    injury_consent: bool = False
    location_consent: bool = False
    coach_visible_consent: bool = False

    model_config = ConfigDict(extra="forbid")


class UserProfileV2Update(BaseModel):
    """PATCH /v1/users/me/profile-v2 请求体."""

    handicap_official: Decimal | None = Field(None, ge=-10, le=54)
    handicap_self: Decimal | None = Field(None, ge=-10, le=54)
    handicap_source: HandicapSourceLiteral | None = None
    height_cm: int | None = Field(None, ge=100, le=250)
    weight_kg: int | None = Field(None, ge=30, le=200)
    handedness: HandednessLiteral | None = None
    known_injuries: list[str] | None = Field(None, max_length=20)
    mid_long_goals: list[str] | None = Field(None, max_length=20)
    training_preference: TrainingPreferenceLiteral | None = None
    # M9-04（alembic 0023_m9_04）：可空 JSONB；显式 None 触发清空
    training_preference_meta: dict | None = None
    weekly_target_sessions: int | None = Field(None, ge=0, le=14)
    # M9-05：常去球馆 ID 列表（venues 表）；upper bound MAX_FAVORITE_VENUES。
    # 服务层 _validate_favorite_venue_ids 还会做 FK-like 存在性校验。
    favorite_course_ids: list[str] | None = Field(None, max_length=MAX_FAVORITE_VENUES)
    privacy_payload: PrivacyPayload | None = None
    coach_visible_fields: list[str] | None = Field(None, max_length=20)

    model_config = ConfigDict(extra="forbid")


class UserProfileV2Read(BaseModel):
    """GET /v1/users/me/profile-v2 响应."""

    user_id: str
    handicap_official: Decimal | None = None
    handicap_self: Decimal | None = None
    handicap_source: HandicapSourceLiteral | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    handedness: HandednessLiteral | None = None
    known_injuries: list[str] = []
    mid_long_goals: list[str] = []
    training_preference: TrainingPreferenceLiteral | None = None
    training_preference_meta: dict | None = None
    weekly_target_sessions: int | None = None
    favorite_course_ids: list[str] = []
    privacy_payload: PrivacyPayload = Field(default_factory=PrivacyPayload)
    coach_visible_fields: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class UserClubCreate(BaseModel):
    """POST /v1/users/me/clubs 请求体."""

    club_type: ClubTypeLiteral
    nickname: str | None = Field(None, max_length=40)
    self_yardage_m: int | None = Field(None, ge=0, le=400)
    is_active: bool = True
    sort_order: int = Field(0, ge=0, le=999)

    model_config = ConfigDict(extra="forbid")


class UserClubUpdate(BaseModel):
    """PATCH /v1/users/me/clubs/{id} 请求体."""

    nickname: str | None = Field(None, max_length=40)
    self_yardage_m: int | None = Field(None, ge=0, le=400)
    is_active: bool | None = None
    sort_order: int | None = Field(None, ge=0, le=999)

    model_config = ConfigDict(extra="forbid")


class UserClubRead(BaseModel):
    """GET /v1/users/me/clubs 列表元素."""

    id: str
    club_type: ClubTypeLiteral
    nickname: str | None = None
    self_yardage_m: int | None = None
    is_active: bool
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class UserClubList(BaseModel):
    """GET /v1/users/me/clubs 响应体."""

    items: list[UserClubRead]
    total: int


# ----------------- M9-06 教练可见性 consent（原子开关 + 字段列表） -----------------


class CoachConsentUpdate(BaseModel):
    """PUT /v1/users/me/profile-v2/coach-consent 请求体（M9-06）.

    与通用 PATCH /me/profile-v2 解耦：教练可见性是一个**原子**决策（开关 + 字段列表
    必须一起决定），独立端点能避免「半开半关」的中间态。

    服务层不变量：
    - ``visible=False`` → 服务器把 ``coach_visible_fields`` 强制清空（PIPL 删除权）
    - ``visible=True``  → ``fields`` 必须非空，否则 ``40022``（开关打开但啥都不让看，
      产品上是没意义的中间态，弹回让用户重新选）
    - ``fields`` 中字段必须在 ``COACH_VISIBLE_ALLOWED`` 白名单内（已有 _validate）
    """

    visible: bool
    fields: list[str] = Field(default_factory=list, max_length=20)

    model_config = ConfigDict(extra="forbid")


class CoachConsentRead(BaseModel):
    """GET /v1/users/me/profile-v2/coach-consent 响应（M9-06）.

    UI 用 ``allowed_fields`` 渲染勾选列表，避免硬编码白名单。
    """

    visible: bool
    fields: list[str] = []
    allowed_fields: list[str] = []


# ----------------- M9-05 常去球馆（展开 venue 详情） -----------------


class FavoriteVenueRead(BaseModel):
    """GET /v1/users/me/profile-v2/favorite-venues 列表元素.

    仅返回必要展示字段；contact / 详细 address 等留给 venue 详情页拉取，避免冗余。
    """

    id: str
    city: str
    name: str
    venue_type: Literal[
        "indoor_range", "outdoor_range", "simulator_lounge", "golf_course"
    ]
    source: Literal["ugc", "verified"]

    model_config = ConfigDict(from_attributes=True)


class FavoriteVenuesList(BaseModel):
    """GET /v1/users/me/profile-v2/favorite-venues 响应体.

    顺序：与 ``favorite_course_ids`` JSONB 数组顺序一致（用户排序意图），
    缺失的 venue（已删除 / closed）在 ``missing_ids`` 单独返回，便于客户端提示。
    """

    items: list[FavoriteVenueRead]
    missing_ids: list[str] = []
    total: int


__all__ = [
    "ClubTypeLiteral",
    "CoachConsentRead",
    "CoachConsentUpdate",
    "FavoriteVenueRead",
    "FavoriteVenuesList",
    "HandednessLiteral",
    "HandicapSourceLiteral",
    "PrivacyPayload",
    "TrainingPreferenceLiteral",
    "UserClubCreate",
    "UserClubList",
    "UserClubRead",
    "UserClubUpdate",
    "UserProfileV2Read",
    "UserProfileV2Update",
]
