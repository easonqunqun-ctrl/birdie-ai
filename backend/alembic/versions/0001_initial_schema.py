"""initial schema: users, analyses, chat

Revision ID: 0001
Revises:
Create Date: 2026-04-18

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ==================== users ====================
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("wechat_openid", sa.String(64), nullable=False),
        sa.Column("wechat_unionid", sa.String(64), nullable=True),
        sa.Column("nickname", sa.String(48), nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("golf_level", sa.String(20), nullable=True),
        sa.Column("primary_goals", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("weekly_practice_frequency", sa.String(20), nullable=True),
        sa.Column("onboarding_completed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("membership_type", sa.String(20), nullable=False, server_default="free"),
        sa.Column("membership_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("membership_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("invite_code", sa.String(8), nullable=False),
        sa.Column("invited_by_user_id", sa.String(32), nullable=True),
        sa.Column("total_analyses", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_practices", sa.Integer, nullable=False, server_default="0"),
        sa.Column("best_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("current_streak_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_streak_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_practice_date", sa.Date, nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("wechat_openid", name="uq_users_openid"),
        sa.UniqueConstraint("invite_code", name="uq_users_invite_code"),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"], ["users.id"], name="fk_users_inviter", ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "golf_level IS NULL OR golf_level IN "
            "('beginner', 'elementary', 'intermediate', 'advanced')",
            name="chk_golf_level",
        ),
        sa.CheckConstraint(
            "weekly_practice_frequency IS NULL OR weekly_practice_frequency "
            "IN ('occasional', 'once', 'frequent', 'daily')",
            name="chk_weekly_frequency",
        ),
        sa.CheckConstraint(
            "membership_type IN ('free', 'monthly', 'yearly', 'family')",
            name="chk_membership_type",
        ),
    )
    op.create_index("idx_users_openid", "users", ["wechat_openid"])
    op.create_index("idx_users_invite_code", "users", ["invite_code"])
    op.create_index("idx_users_created_at", "users", ["created_at"])
    op.create_index(
        "idx_users_membership",
        "users",
        ["membership_type", "membership_expires_at"],
        postgresql_where=sa.text("membership_type != 'free'"),
    )
    op.create_index(
        "idx_users_alive",
        "users",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ==================== analysis_quotas ====================
    op.create_table(
        "analysis_quotas",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("quota_month", sa.String(7), nullable=False),
        sa.Column("used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total", sa.Integer, nullable=False, server_default="3"),
        sa.Column("bonus", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "quota_month", name="uq_analysis_quota"),
    )
    op.create_index("idx_analysis_quotas_lookup", "analysis_quotas", ["user_id", "quota_month"])

    # ==================== swing_analyses ====================
    op.create_table(
        "swing_analyses",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("video_url", sa.String(512), nullable=False),
        sa.Column("video_duration", sa.Numeric(5, 2), nullable=True),
        sa.Column("video_file_size", sa.BigInteger, nullable=True),
        sa.Column("camera_angle", sa.String(20), nullable=False),
        sa.Column("club_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("stage", sa.String(30), nullable=True),
        sa.Column("stage_progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_code", sa.Integer, nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("quota_refunded", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("priority", sa.String(10), nullable=False, server_default="standard"),
        sa.Column("overall_score", sa.Integer, nullable=True),
        sa.Column("score_change", sa.Integer, nullable=True),
        sa.Column("phase_scores", postgresql.JSONB, nullable=True),
        sa.Column("phase_timestamps", postgresql.JSONB, nullable=True),
        sa.Column("skeleton_video_url", sa.String(512), nullable=True),
        sa.Column("skeleton_data_url", sa.String(512), nullable=True),
        sa.Column("thumbnail_url", sa.String(512), nullable=True),
        sa.Column("share_card_url", sa.String(512), nullable=True),
        sa.Column("is_sample", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_swing_analyses_user", "swing_analyses", ["user_id", "created_at"])
    op.create_index("idx_swing_analyses_status", "swing_analyses", ["status"])

    # ==================== analysis_issues ====================
    op.create_table(
        "analysis_issues",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("analysis_id", sa.String(32), nullable=False),
        sa.Column("issue_type", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("key_frame_url", sa.String(512), nullable=True),
        sa.Column("key_frame_timestamp", sa.Numeric(5, 2), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["analysis_id"], ["swing_analyses.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_analysis_issues_analysis", "analysis_issues", ["analysis_id"])

    # ==================== analysis_recommendations ====================
    op.create_table(
        "analysis_recommendations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("analysis_id", sa.String(32), nullable=False),
        sa.Column("drill_id", sa.String(40), nullable=False),
        sa.Column("target_issue", sa.String(40), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["analysis_id"], ["swing_analyses.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_analysis_recs_analysis", "analysis_recommendations", ["analysis_id"])

    # ==================== chat_quotas ====================
    op.create_table(
        "chat_quotas",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("quota_date", sa.Date, nullable=False),
        sa.Column("used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total", sa.Integer, nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "quota_date", name="uq_chat_quota"),
    )
    op.create_index("idx_chat_quotas_lookup", "chat_quotas", ["user_id", "quota_date"])

    # ==================== chat_sessions ====================
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("context_analysis_id", sa.String(32), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["context_analysis_id"], ["swing_analyses.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("idx_chat_sessions_user", "chat_sessions", ["user_id", "last_message_at"])

    # ==================== chat_messages ====================
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("session_id", sa.String(32), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.String(4000), nullable=False),
        sa.Column("attachments", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_chat_messages_session", "chat_messages", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("chat_quotas")
    op.drop_table("analysis_recommendations")
    op.drop_table("analysis_issues")
    op.drop_table("swing_analyses")
    op.drop_table("analysis_quotas")
    op.drop_table("users")
