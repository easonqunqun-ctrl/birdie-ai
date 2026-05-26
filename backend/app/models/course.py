"""二期 M11 课程体系数据模型（对齐 docs/23 §7.1 / docs/03 §8.4 v0.1）.

4 张表
------
- ``courses``：7 阶课程（stage 1-7）+ 会员可见性 + 教练定制（``created_by_user_id``）
- ``lessons``：单课时（视频 + drill_ids 引用一期 drill 库 + 测验 + pass_criteria）
- ``user_course_progress``：lesson 维度状态机（not_started/in_progress/passed/failed）
- ``course_certificates``：通关证书（``cert_url`` 复用一期 M5 海报合成）

与一期共存
---------
本模块**不替代** ``drills`` / ``training_plans``，而是更高层"教学路径"封装：
``lessons.drill_ids`` JSONB 数组引用 ``drills.id``，引用关系走应用层 service 校验
（drills 是 seed 表，不在 DB 加 FK，避免循环依赖与 seed 灵活性损失）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Course(Base, TimestampMixin):
    """7 阶课程（M11-01）."""

    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # crs_<nanoid>
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    stage: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_member_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objectives: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    estimated_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60"
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("users.id"), nullable=True
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lessons: Mapped[list[Lesson]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="Lesson.sort_order",
    )

    __table_args__ = (
        CheckConstraint("stage BETWEEN 1 AND 7", name="chk_courses_stage"),
        Index(
            "idx_courses_stage",
            "stage",
            "sort_order",
            postgresql_where="is_published = TRUE",
        ),
        Index("idx_courses_member", "is_member_only", "stage"),
    )

    def __repr__(self) -> str:
        return f"<Course {self.id} stage={self.stage} {self.code}>"


class Lesson(Base, TimestampMixin):
    """单课时（M11-01 / M11-02）."""

    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # lsn_<nanoid>
    course_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=15, server_default="15"
    )
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    drill_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    pro_clip_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    quiz_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pass_criteria: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    course = relationship("Course", back_populates="lessons", lazy="noload")

    __table_args__ = (
        UniqueConstraint("course_id", "sort_order", name="uq_lessons_course_sort"),
        Index("idx_lessons_course_id", "course_id", "sort_order"),
    )

    def __repr__(self) -> str:
        return f"<Lesson {self.id} course={self.course_id} #{self.sort_order}>"


class UserCourseProgress(Base, TimestampMixin):
    """lesson 维度的用户进度（M11-01 / M11-04 状态机）."""

    __tablename__ = "user_course_progress"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # ucp_<nanoid>
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    lesson_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_started", server_default="'not_started'"
    )
    last_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_reasons: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_ucp_user_lesson"),
        CheckConstraint(
            "status IN ('not_started', 'in_progress', 'passed', 'failed')",
            name="chk_ucp_status",
        ),
        Index(
            "idx_ucp_user_passed",
            "user_id",
            "status",
            postgresql_where="status = 'passed'",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserCourseProgress user={self.user_id} lesson={self.lesson_id} {self.status}>"


class CourseCertificate(Base):
    """通关证书（M11-05；cert_url 来自 M5 海报合成）."""

    __tablename__ = "course_certificates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # crt_<nanoid>
    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    cert_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()"
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",  # 列名沿用 docs/23 §7.1 设计；Python 属性避开 SQLAlchemy ``metadata`` 关键字
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    __table_args__ = (
        CheckConstraint("stage BETWEEN 1 AND 7", name="chk_cc_stage"),
        Index(
            "uq_cc_user_course",
            "user_id",
            "course_id",
            unique=True,
            postgresql_where="revoked_at IS NULL",
        ),
        Index("idx_cc_user_issued", "user_id", "issued_at"),
    )

    def __repr__(self) -> str:
        return f"<CourseCertificate user={self.user_id} course={self.course_id} stage={self.stage}>"


# ---------------- 服务层共用常量 ----------------
COURSE_STATUS_NOT_STARTED = "not_started"
COURSE_STATUS_IN_PROGRESS = "in_progress"
COURSE_STATUS_PASSED = "passed"
COURSE_STATUS_FAILED = "failed"

VALID_COURSE_STATUSES: frozenset[str] = frozenset(
    {
        COURSE_STATUS_NOT_STARTED,
        COURSE_STATUS_IN_PROGRESS,
        COURSE_STATUS_PASSED,
        COURSE_STATUS_FAILED,
    }
)

# 状态机合法迁移：from → 允许的 to 集合
VALID_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    COURSE_STATUS_NOT_STARTED: frozenset({COURSE_STATUS_IN_PROGRESS}),
    COURSE_STATUS_IN_PROGRESS: frozenset(
        {COURSE_STATUS_PASSED, COURSE_STATUS_FAILED, COURSE_STATUS_IN_PROGRESS}
    ),
    COURSE_STATUS_FAILED: frozenset({COURSE_STATUS_IN_PROGRESS}),
    COURSE_STATUS_PASSED: frozenset(),  # 终态
}

# stage 总阶数（用于升阶判定 / 证书）
MAX_STAGE = 7


__all__ = [
    "COURSE_STATUS_FAILED",
    "COURSE_STATUS_IN_PROGRESS",
    "COURSE_STATUS_NOT_STARTED",
    "COURSE_STATUS_PASSED",
    "MAX_STAGE",
    "VALID_COURSE_STATUSES",
    "VALID_STATUS_TRANSITIONS",
    "Course",
    "CourseCertificate",
    "Lesson",
    "UserCourseProgress",
]
