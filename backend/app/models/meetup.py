"""二期 M13 球友约球数据模型（对齐 docs/23 §9.1 / docs/06 §13.4）.

5 张表
------
- ``venues``：球场 / 室内打位（UGC + 运营审核两路）
- ``meetup_invitations``：一对一 / 小型约球邀请（含 ``contact_payload`` 仅在 accepted
  后写入）
- ``meetup_feedbacks``：双向反馈 + 信用分（M13-07）
- ``self_organized_events``：自组织小挑战（M13-08；**无奖金 / 无实物奖品**）
- ``event_participations``：报名参与

合规硬约束（docs/06 §13.4）
---------------------------
- ``meetup_invitations.contact_payload`` 写入前必须通过 ``write_contact_payload()``
  正则守门，**禁止**写 ``openid`` / 手机号正则匹配字符串
- ``self_organized_events`` 没有 ``reward_cash`` / ``reward_item`` 字段（M13-08
  kickoff §3）
- 自约球年龄门槛 14 岁 + 实名手机号（M13-09 kickoff §3，运行时 check）

CASCADE
-------
``users → meetup_invitations / meetup_feedbacks / event_participations``：账号注销
时联动清理。``venues`` 不直接 CASCADE 删除参与记录，``status='closed'`` 软隔离。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Venue(Base, TimestampMixin):
    """球场 / 打位（UGC 与运营两路并行）.

    地理信息（M13-02 alembic 0024 加列）
    -----------------------------------
    ``latitude`` / ``longitude`` 是可选 ``Numeric(9,6)`` 列：
    - 精度 6 位小数 = 约 11cm，对"找最近 5 个球场"绝对够用
    - 范围 lat ∈ [-90, 90], lng ∈ [-180, 180] 由 CHECK 兜底
    - 都为 NULL 时 venue 不出现在 nearby 搜索结果里（接受软覆盖率代价，
      避免 GPS 缺失场地被算成 0,0 → 几内亚湾鬼影）
    """

    __tablename__ = "venues"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # ven_<nanoid>
    city: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    venue_type: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # M13-02：可选地理坐标（NULL → 不进入 nearby 结果）
    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6), nullable=True
    )
    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6), nullable=True
    )
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ugc", server_default="'ugc'"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="'active'"
    )
    contributor_user_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "venue_type IN ('indoor_range', 'outdoor_range', 'simulator_lounge', 'golf_course')",
            name="chk_venue_type",
        ),
        CheckConstraint(
            "source IN ('ugc', 'verified')",
            name="chk_venue_source",
        ),
        CheckConstraint(
            "status IN ('active', 'flagged', 'closed')",
            name="chk_venue_status",
        ),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)",
            name="chk_venue_geo_range",
        ),
        Index("idx_venues_city_status", "city", "status"),
        # 经纬度联合索引：nearby 查询先按 status 过滤再按 lat/lng 范围；
        # B-tree 联合在 lat 区间 + lng 区间扫描下比单列优，对中小数据集足够。
        Index(
            "idx_venues_geo",
            "latitude",
            "longitude",
            postgresql_where="status = 'active' AND latitude IS NOT NULL",
        ),
    )


class MeetupInvitation(Base, TimestampMixin):
    """一对一 / 小型约球邀请."""

    __tablename__ = "meetup_invitations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # mvi_<nanoid>
    inviter_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    invitee_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    venue_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("venues.id"),
        nullable=True,
    )
    proposed_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="'pending'"
    )
    contact_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    risk_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'expired', 'cancelled')",
            name="chk_mvi_status",
        ),
        CheckConstraint(
            "inviter_user_id != invitee_user_id",
            name="chk_no_self_invite",
        ),
        Index("idx_mvi_invitee_status", "invitee_user_id", "status"),
        Index("idx_mvi_inviter_status", "inviter_user_id", "status"),
    )


class MeetupFeedback(Base, TimestampMixin):
    """约球后的双向反馈 + 信用分（M13-07）.

    ``rating`` ∈ {1, 2, 3, 4, 5}；``credit_delta`` 范围 [-10, +10]，服务层按
    ``rating`` + ``tags`` 计算。
    """

    __tablename__ = "meetup_feedbacks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # mfb_<nanoid>
    invitation_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("meetup_invitations.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewee_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tags: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    credit_delta: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="chk_mfb_rating"),
        CheckConstraint(
            "credit_delta BETWEEN -20 AND 20",
            name="chk_mfb_credit_delta",
        ),
        CheckConstraint(
            "reviewer_user_id != reviewee_user_id",
            name="chk_mfb_no_self",
        ),
        UniqueConstraint(
            "invitation_id",
            "reviewer_user_id",
            name="uq_mfb_invitation_reviewer",
        ),
        Index("idx_mfb_reviewee", "reviewee_user_id", "created_at"),
        Index("idx_mfb_invitation", "invitation_id"),
    )


class SelfOrganizedEvent(Base, TimestampMixin):
    """自组织小挑战（M13-08）.

    刻意**不**包含任何 ``reward_cash`` / ``reward_item`` 字段，奖励只能是徽章
    （走 ``course_certificates`` 表 ``scope='meetup_event'`` 复用，M11-05 框架）。
    """

    __tablename__ = "self_organized_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # soe_<nanoid>
    organizer_user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    venue_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("venues.id"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="'draft'"
    )
    # 仅徽章型激励，不允许现金 / 实物
    badge_template_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rules_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    moderation_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'open', 'closed', 'cancelled', 'completed')",
            name="chk_soe_status",
        ),
        CheckConstraint(
            "capacity IS NULL OR (capacity BETWEEN 1 AND 200)",
            name="chk_soe_capacity",
        ),
        Index("idx_soe_status_time", "status", "scheduled_at"),
    )


class EventParticipation(Base, TimestampMixin):
    """报名记录（M13-08）."""

    __tablename__ = "event_participations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("self_organized_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="signed_up",
        server_default="'signed_up'",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    score_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('signed_up', 'checked_in', 'completed', 'no_show', 'cancelled')",
            name="chk_evp_status",
        ),
        UniqueConstraint("event_id", "user_id", name="uq_evp_event_user"),
        Index("idx_evp_event_status", "event_id", "status"),
        Index("idx_evp_user", "user_id", "created_at"),
    )


# ============================================================================
# 合规：反联系方式硬约束（docs/06 §13.4）
# ============================================================================

# 11 位手机号 + WeChat openid 风格关键字 + 通用社交账号字段
_CONTACT_LEAK_PATTERNS = [
    re.compile(r"1[3-9]\d{9}"),
    re.compile(r"openid", re.IGNORECASE),
    re.compile(r"unionid", re.IGNORECASE),
    re.compile(r"wx_[a-z0-9_]+"),
    re.compile(r"\b\d{6,8}@qq\.com\b"),
]

_FORBIDDEN_KEYS = frozenset({"openid", "unionid", "phone", "mobile", "wechat_id"})


class ContactPayloadComplianceError(Exception):
    """``contact_payload`` 写入含禁字 / 禁字段时抛出（hook 进 BadRequestError）."""


def _contains_forbidden_keys(payload: dict) -> str | None:
    for k in payload:
        if k.lower() in _FORBIDDEN_KEYS:
            return k
    return None


def write_contact_payload(invitation: MeetupInvitation, payload: dict) -> None:
    """合规守门：邀请 accepted 后再写联系方式，禁止 openid / 手机号正则.

    用法（service 层）::

        invitation.status = 'accepted'
        write_contact_payload(invitation, {'note': '今晚 7 点海门一号场地见'})

    凡入参 ``payload`` 直接 JSON 序列化后被任何 ``_CONTACT_LEAK_PATTERNS``
    命中、或 key 命中 ``_FORBIDDEN_KEYS``，立即抛 ``ContactPayloadComplianceError``。
    """

    if not isinstance(payload, dict):
        raise ContactPayloadComplianceError("contact_payload 必须是 dict")
    bad_key = _contains_forbidden_keys(payload)
    if bad_key:
        raise ContactPayloadComplianceError(
            f"contact_payload 含禁字段：{bad_key}（详 docs/06 §13.4）"
        )
    raw = json.dumps(payload, ensure_ascii=False)
    for pat in _CONTACT_LEAK_PATTERNS:
        m = pat.search(raw)
        if m:
            raise ContactPayloadComplianceError(
                f"contact_payload 命中联系方式正则：{m.group()[:6]}***"
            )
    invitation.contact_payload = dict(payload)


VALID_VENUE_TYPES: frozenset[str] = frozenset(
    {"indoor_range", "outdoor_range", "simulator_lounge", "golf_course"}
)
VALID_INVITATION_STATUSES: frozenset[str] = frozenset(
    {"pending", "accepted", "declined", "expired", "cancelled"}
)
VALID_EVENT_STATUSES: frozenset[str] = frozenset(
    {"draft", "open", "closed", "cancelled", "completed"}
)

# 自约球年龄门槛 + 实名要求（M13-09）
MIN_MEETUP_AGE = 14


__all__ = [
    "MIN_MEETUP_AGE",
    "VALID_EVENT_STATUSES",
    "VALID_INVITATION_STATUSES",
    "VALID_VENUE_TYPES",
    "ContactPayloadComplianceError",
    "EventParticipation",
    "MeetupFeedback",
    "MeetupInvitation",
    "SelfOrganizedEvent",
    "Venue",
    "write_contact_payload",
]
