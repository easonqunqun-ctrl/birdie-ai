"""用户模型（对齐 docs/03-数据库设计文档.md 3.1 节）."""

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # usr_<nanoid>

    # 微信身份（小程序与 App OpenID 不同；至少填其一）
    # 唯一性：非空时在 DB 上以部分 UNIQUE 索引保证（Alembic 0009）。
    wechat_openid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wechat_app_openid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wechat_unionid: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 资料
    nickname: Mapped[str | None] = mapped_column(String(48), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # 高尔夫档案
    golf_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    primary_goals: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    weekly_practice_frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # MVP §3.6 O-03：任意非示例分析曾达 completed 后置 true，用于首页隐藏「示例报告」入口
    has_completed_real_analysis: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    # 会员
    membership_type: Mapped[str] = mapped_column(String(20), default="free", server_default="'free'")
    membership_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    membership_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Q-B5：委托代扣签约成功后微信返回的 contract_id（仅真实开通后非空）
    papay_contract_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 邀请
    invite_code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    invited_by_user_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 统计缓存
    total_analyses: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_practices: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    best_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    current_streak_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_streak_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_practice_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # M13-06 约球信用分（初始 100；M13-07 互评驱动增减）
    meetup_credit_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )

    # M13-09 约球实名 / 未成年保护 / 女性安全匹配
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # 账号注销（MVP §3.4）：非空且 <= now 时清理；两条触发路径：
    #   1) 懒清理：`get_user_by_id` 用户下次发请求时触发（`user_service.py`）
    #   2) Beat 兜底：`xiaoniao.purge_due_account_deletions` 每小时扫一次（`tasks/account_tasks.py`），
    #      用户即便不再登录也能按 PIPL 承诺如期清掉
    account_deletion_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 关系（按需启用 lazy="selectin"）
    analyses: Mapped[list["SwingAnalysis"]] = relationship(  # noqa: F821
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        CheckConstraint(
            "golf_level IS NULL OR golf_level IN ('beginner', 'elementary', 'intermediate', 'advanced')",
            name="chk_golf_level",
        ),
        CheckConstraint(
            "weekly_practice_frequency IS NULL OR weekly_practice_frequency "
            "IN ('occasional', 'once', 'frequent', 'daily')",
            name="chk_weekly_frequency",
        ),
        CheckConstraint(
            "membership_type IN ('free', 'monthly', 'yearly', 'family')",
            name="chk_membership_type",
        ),
        CheckConstraint(
            "meetup_credit_score BETWEEN 0 AND 100",
            name="chk_users_meetup_credit_score",
        ),
        CheckConstraint(
            "gender IS NULL OR gender IN ('female', 'male', 'other')",
            name="chk_users_gender",
        ),
        Index("idx_users_invite_code", "invite_code"),
        Index(
            "idx_users_membership",
            "membership_type",
            "membership_expires_at",
            postgresql_where="membership_type != 'free'",
        ),
        Index("idx_users_created_at", "created_at"),
        Index("idx_users_alive", "deleted_at", postgresql_where="deleted_at IS NULL"),
    )

    def __repr__(self) -> str:
        oid = self.nickname or self.wechat_openid or self.wechat_app_openid
        return f"<User {self.id} {oid}>"

    def wechat_subject_for_jwt(self) -> str:
        """JWT `openid` 声明：小程序 openid 优先，否则回落到 App openid."""
        oid = self.wechat_openid or self.wechat_app_openid
        if not oid:
            raise RuntimeError("user identity missing both wechat identifiers")
        return oid
