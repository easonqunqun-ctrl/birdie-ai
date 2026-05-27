"""二期 M9 画像 2.0 数据模型（对齐 docs/23 §5.1 / docs/03 §8.3 v0.1）.

为什么不扩 ``users`` 表
----------------------
- 一期 ``users`` 表是「小程序登录 + 简单档案 + 会员」最小模型，二期画像 2.0 需要
  真实差点 / 身体数据 / 利手 / 已知伤病 / 装备清单等深度字段，且每个字段独立同
  意位。直接扩列会让一期接口契约的字段集合越长越乱，GDPR 字段级清理时也难
  以精准定位。
- 因此采用「**一对一扩展表 + 独立隐私载荷**」模式，本表与 ``users`` 通过
  ``user_id`` 1:1 关联，``ON DELETE CASCADE`` 确保账号注销时同步清掉。

字段级同意位（FR-3）
-----------------
``privacy_payload`` JSONB 维护以下 5 个 consent 字段（缺省 false）：

- ``handicap_consent``：真实差点
- ``body_consent``：身高 / 体重
- ``injury_consent``：已知伤病（高敏感，详 docs/06 §13.1，**禁止透传 LLM**）
- ``location_consent``：常去球馆（M13 约球前置）
- ``coach_visible_consent``：教练侧可见总开关（M9-06 配合 ``coach_visible_fields``
  白名单使用）

服务层在读取 / 写入对应列前必须先校验 consent；consent 为 false 时清空对应列。

灰度
----
通过 ``PHASE2_PROFILE_V2_ENABLED`` feature flag 控制 API 暴露，本表自身的 CREATE
TABLE 是「零 downtime 兼容」，可以提前上线只不开放写入。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserProfileV2(Base, TimestampMixin):
    """``users`` 表的一对一深度档案扩展（M9-01）."""

    __tablename__ = "user_profiles_v2"

    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # 真实差点（M9-03）
    handicap_official: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    handicap_self: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    handicap_source: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 身体数据（M9-03，敏感等级"高"，docs/06 §13.1）
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    handedness: Mapped[str | None] = mapped_column(String(10), nullable=True)
    known_injuries: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # 目标 / 偏好（M9-04）
    mid_long_goals: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    training_preference: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # M9-04（alembic 0023_m9_04）：cadence + preferred_drill_types
    # {"cadence": "daily"|"2x_per_week"|"weekly", "preferred_drill_types": ["rhythm", ...]}
    training_preference_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    weekly_target_sessions: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 常去球馆（M9-05；M13 约球前置）
    favorite_course_ids: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # 字段级隐私载荷（FR-3）
    privacy_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    # 教练侧只读视图授权（M9-06 白名单）
    coach_visible_fields: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    __table_args__ = (
        CheckConstraint(
            "handedness IS NULL OR handedness IN ('right', 'left', 'switch')",
            name="chk_user_profiles_v2_handedness",
        ),
        CheckConstraint(
            "handicap_official IS NULL OR (handicap_official BETWEEN -10 AND 54)",
            name="chk_user_profiles_v2_handicap_official",
        ),
        CheckConstraint(
            "handicap_self IS NULL OR (handicap_self BETWEEN -10 AND 54)",
            name="chk_user_profiles_v2_handicap_self",
        ),
        CheckConstraint(
            "handicap_source IS NULL OR handicap_source IN ('rcga', 'usga', 'self')",
            name="chk_user_profiles_v2_handicap_source",
        ),
        CheckConstraint(
            "training_preference IS NULL OR training_preference IN ('video', 'text', 'mixed')",
            name="chk_user_profiles_v2_training_preference",
        ),
        CheckConstraint(
            "height_cm IS NULL OR (height_cm BETWEEN 100 AND 250)",
            name="chk_user_profiles_v2_height_cm",
        ),
        CheckConstraint(
            "weight_kg IS NULL OR (weight_kg BETWEEN 30 AND 200)",
            name="chk_user_profiles_v2_weight_kg",
        ),
        CheckConstraint(
            "weekly_target_sessions IS NULL OR (weekly_target_sessions BETWEEN 0 AND 14)",
            name="chk_user_profiles_v2_weekly_target_sessions",
        ),
        Index("idx_user_profiles_v2_updated_at", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<UserProfileV2 user_id={self.user_id}>"


class UserClub(Base, TimestampMixin):
    """用户装备清单一行 = 一支球杆（M9-01 / M9-02）.

    每用户最多 14 支：DB 层不强约束（保留性能），服务层 ``add_club()`` 显式校验
    并抛 ``BadRequestError``。
    """

    __tablename__ = "user_clubs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # ucb_<nanoid>
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    club_type: Mapped[str] = mapped_column(String(20), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(40), nullable=True)
    self_yardage_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    __table_args__ = (
        CheckConstraint(
            "self_yardage_m IS NULL OR (self_yardage_m BETWEEN 0 AND 400)",
            name="chk_user_clubs_self_yardage_m",
        ),
        Index("idx_user_clubs_user_id", "user_id"),
        Index("idx_user_clubs_user_active", "user_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<UserClub {self.id} user={self.user_id} type={self.club_type}>"


# 服务层校验用常量：单用户装备清单最大条数
MAX_CLUBS_PER_USER = 14

# 服务层校验：常去球馆（venues）最多条数（M9-05；M13 约球前置）。
# 设 6 而非 20：避免「列表式社交骚扰」，引导用户精选高频场地；
# UI 端表现为 chip 选择上限，溢出时禁用未选项 + Toast。
MAX_FAVORITE_VENUES = 6

# privacy_payload 合法 consent 字段集合（详 docs/23 §5.1 FR-3）
CONSENT_FIELDS: frozenset[str] = frozenset(
    {
        "handicap_consent",
        "body_consent",
        "injury_consent",
        "location_consent",
        "coach_visible_consent",
    }
)

# coach_visible_fields 合法字段白名单（M9-06 配合使用）
COACH_VISIBLE_ALLOWED: frozenset[str] = frozenset(
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
        "weekly_target_sessions",
        "favorite_course_ids",
    }
)


__all__ = [
    "COACH_VISIBLE_ALLOWED",
    "CONSENT_FIELDS",
    "MAX_CLUBS_PER_USER",
    "MAX_FAVORITE_VENUES",
    "UserClub",
    "UserProfileV2",
]
