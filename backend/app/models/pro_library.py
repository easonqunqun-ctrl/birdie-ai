"""二期 M12 职业球手对比库数据模型（对齐 docs/23 §8.1 / docs/03 §8.5 v0.1）.

6 张表
------
- ``pro_players``：球手主表（含 license_status 默认值）
- ``pro_swing_clips``：球手镜头 + features_snapshot + source_credit
- ``pro_clip_annotations``：教练 PGC 解说（含时间锚点）
- ``pro_topics``：每周精选（一组 clip 的封装）
- ``user_pro_favorites``：用户收藏（联合主键）
- ``user_pro_match_history``：「和你最像的」匹配历史

合规守门
-------
- ``license_status`` 三态 CHECK：``public_clip`` / ``authorized`` / ``partnership``
- ``source_credit`` / ``source_url`` NOT NULL（任何镜头入库必须可追源）

CASCADE 链路
-----------
``pro_players → pro_swing_clips → (pro_clip_annotations | user_pro_favorites |
user_pro_match_history)`` 全程 ``ON DELETE CASCADE``。``pro_clip_annotations.
author_user_id`` 走 ``RESTRICT`` 不让删教练时把解说连带丢，需先把 author 改为
其他官方账号或 null。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ProPlayer(Base, TimestampMixin):
    """球手主表."""

    __tablename__ = "pro_players"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # pp_<nanoid>
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(80), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(3), nullable=True)
    handedness: Mapped[str] = mapped_column(String(10), nullable=False)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    short_bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="public_clip", server_default="'public_clip'"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    clips: Mapped[list[ProSwingClip]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        CheckConstraint(
            "license_status IN ('public_clip', 'authorized', 'partnership')",
            name="chk_pp_license",
        ),
        CheckConstraint("handedness IN ('right', 'left')", name="chk_pp_handedness"),
        Index("idx_pp_active_sort", "is_active", "sort_order"),
    )


class ProSwingClip(Base, TimestampMixin):
    """球手单条镜头."""

    __tablename__ = "pro_swing_clips"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # psc_<nanoid>
    pro_player_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("pro_players.id", ondelete="CASCADE"),
        nullable=False,
    )
    club_type: Mapped[str] = mapped_column(String(20), nullable=False)
    camera_angle: Mapped[str] = mapped_column(String(20), nullable=False)
    video_url: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="v1", server_default="'v1'"
    )
    features_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    phase_timestamps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 版权
    license_status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_credit: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(String(512), nullable=False)
    captured_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    player = relationship("ProPlayer", back_populates="clips", lazy="noload")

    __table_args__ = (
        CheckConstraint(
            "camera_angle IN ('face_on', 'down_the_line')",
            name="chk_psc_camera",
        ),
        CheckConstraint(
            "license_status IN ('public_clip', 'authorized', 'partnership')",
            name="chk_psc_license",
        ),
        Index("idx_psc_player", "pro_player_id", "club_type"),
        Index(
            "idx_psc_published",
            "is_published",
            "club_type",
            postgresql_where="is_published = TRUE",
        ),
    )


class ProClipAnnotation(Base, TimestampMixin):
    """教练 PGC 解说."""

    __tablename__ = "pro_clip_annotations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    clip_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("pro_swing_clips.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    annotation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_marker_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    is_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    __table_args__ = (
        CheckConstraint(
            "annotation_type IN ('text', 'voice', 'sketch')",
            name="chk_pca_type",
        ),
        Index("idx_pca_clip", "clip_id", "time_marker_ms"),
    )


class ProTopic(Base, TimestampMixin):
    """每周精选."""

    __tablename__ = "pro_topics"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # pt_<nanoid>
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    clip_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    week_starts_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_pt_published", "is_published", "week_starts_at"),
    )


class UserProFavorite(Base):
    """用户收藏（联合主键）."""

    __tablename__ = "user_pro_favorites"

    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    clip_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("pro_swing_clips.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="NOW()",
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_task_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("training_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index("idx_upf_user", "user_id", "created_at"),
        Index("idx_upf_training_task", "training_task_id"),
    )


class UserProMatchHistory(Base):
    """"和你最像的"匹配历史."""

    __tablename__ = "user_pro_match_history"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("swing_analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    matched_clip_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("pro_swing_clips.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    match_details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="NOW()",
    )

    __table_args__ = (
        Index("idx_upmh_user", "user_id", "created_at"),
        Index("idx_upmh_analysis", "analysis_id"),
    )


# 服务层 / 路由层共用常量
VALID_LICENSE_STATUSES: frozenset[str] = frozenset(
    {"public_clip", "authorized", "partnership"}
)
VALID_CAMERA_ANGLES: frozenset[str] = frozenset({"face_on", "down_the_line"})
VALID_ANNOTATION_TYPES: frozenset[str] = frozenset({"text", "voice", "sketch"})


__all__ = [
    "VALID_ANNOTATION_TYPES",
    "VALID_CAMERA_ANGLES",
    "VALID_LICENSE_STATUSES",
    "ProClipAnnotation",
    "ProPlayer",
    "ProSwingClip",
    "ProTopic",
    "UserProFavorite",
    "UserProMatchHistory",
]
