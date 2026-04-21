"""训练计划 / 动作库 / 打卡日志模型（对齐 docs/03 §3.7-3.10）.

W7-T3 关键点：
- `drills` 是**静态业务数据表**，通过 seed 初始化 13 条动作（与
  `client/src/constants/drillLibrary.ts` 完全对齐）；不依赖用户数据
- `training_plans` 按"自然周"维度（周一到周日）分组，`uq_user_week` 保证
  同一周不重复建 plan —— `generate_or_update_weekly` 做 upsert
- `training_tasks` 是 plan 的子项，`drill_id` 关联 drills；完成后写 `practice_logs`
- `practice_logs` 面向用户维度查"某日练过什么"，也是 streak 计算的事实源
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Drill(Base, TimestampMixin):
    """动作库（训练动作）— 静态业务数据，通过 seed 导入."""

    __tablename__ = "drills"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # drill_<snake>
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)

    target_issues: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    tips: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    sets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False)

    illustration_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    __table_args__ = (
        CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="chk_drill_difficulty",
        ),
    )


class TrainingPlan(Base, TimestampMixin):
    """周度训练计划."""

    __tablename__ = "training_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # plan_<nanoid>
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)

    source_analysis_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("swing_analyses.id", ondelete="SET NULL"),
        nullable=True,
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_tasks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    completed_tasks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    tasks: Mapped[list["TrainingTask"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="uq_user_week"),
        Index("idx_plans_user_week", "user_id", "week_start"),
    )


class TrainingTask(Base, TimestampMixin):
    """训练任务项（plan 的子任务）."""

    __tablename__ = "training_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("training_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    drill_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("drills.id"),
        nullable=False,
    )

    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="'pending'")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_analysis_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("swing_analyses.id", ondelete="SET NULL"),
        nullable=True,
    )

    plan = relationship("TrainingPlan", back_populates="tasks", lazy="noload")

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'completed')", name="chk_task_status"),
        Index("idx_tasks_plan", "plan_id"),
        Index("idx_tasks_user_date", "user_id", "scheduled_date"),
        Index("idx_tasks_user_status", "user_id", "status", "scheduled_date"),
    )


class PracticeLog(Base):
    """练习打卡日志。streak 统计 / 进步曲线（W8）均来自此表."""

    __tablename__ = "practice_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("training_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    drill_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("drills.id"),
        nullable=False,
    )

    practice_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )

    __table_args__ = (
        Index("idx_practice_user_date", "user_id", "practice_date"),
    )
