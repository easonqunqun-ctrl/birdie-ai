"""二期 M11 课程服务（对齐 docs/23 §7.1）.

职责
----
- 课程 / 课时 CRUD（service 层校验 drill_ids / pro_clip_ids 引用）
- ``user_course_progress`` 状态机推进（含合法迁移校验）
- 升阶判定 + 证书生成钩子（M11-04 落地具体海报合成，M11-05 接 cert_url）

刻意不做
-------
- 路由层（路由由 M11-03 PR 引入；本 PR 仅交付 service / model）
- 海报合成（复用 M5；本 PR 只生成 ``CourseCertificate`` 占位行）
- 阶段升级触发训练计划补丁（M11-04 决定是否做）
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.course import (
    COURSE_STATUS_IN_PROGRESS,
    COURSE_STATUS_PASSED,
    MAX_STAGE,
    VALID_STATUS_TRANSITIONS,
    Course,
    CourseCertificate,
    Lesson,
    UserCourseProgress,
)
from app.models.training import Drill
from app.schemas.course import (
    CourseCreate,
    LessonCreate,
    UserCourseProgressUpdate,
)

logger = get_logger("course")


# ---------------- 课程 ----------------


async def get_course(db: AsyncSession, course_id: str) -> Course | None:
    row = await db.execute(select(Course).where(Course.id == course_id))
    return row.scalar_one_or_none()


async def list_published_courses(
    db: AsyncSession, *, stage: int | None = None
) -> list[Course]:
    stmt = select(Course).where(Course.is_published.is_(True))
    if stage is not None:
        stmt = stmt.where(Course.stage == stage)
    stmt = stmt.order_by(Course.stage.asc(), Course.sort_order.asc())
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def create_course(db: AsyncSession, payload: CourseCreate) -> Course:
    course = Course(
        id=new_id("crs"),
        code=payload.code,
        title=payload.title,
        subtitle=payload.subtitle,
        cover_url=payload.cover_url,
        stage=payload.stage,
        sort_order=payload.sort_order,
        is_member_only=payload.is_member_only,
        description=payload.description,
        learning_objectives=list(payload.learning_objectives),
        estimated_minutes=payload.estimated_minutes,
        created_by_user_id=payload.created_by_user_id,
    )
    db.add(course)
    await db.flush()
    logger.info("course_created", course_id=course.id, stage=course.stage)
    return course


async def publish_course(db: AsyncSession, course_id: str) -> Course:
    course = await get_course(db, course_id)
    if course is None:
        raise NotFoundError(code=40406, message="课程不存在")
    if course.is_published:
        return course
    # 发布前必须有至少 1 节课
    cnt = await db.execute(
        select(func.count(Lesson.id)).where(Lesson.course_id == course_id)
    )
    if (cnt.scalar_one() or 0) == 0:
        raise BadRequestError(code=40010, message="课程下尚无课时，无法发布")

    # 发布前校验所有 lesson 的 drill_ids 引用都有效
    lessons_q = await db.execute(
        select(Lesson.drill_ids).where(Lesson.course_id == course_id)
    )
    referenced: set[str] = set()
    for row in lessons_q.all():
        referenced.update(row[0] or [])
    if referenced:
        await _validate_drill_ids(db, referenced)

    course.is_published = True
    course.published_at = datetime.now(UTC)
    await db.flush()
    logger.info("course_published", course_id=course.id)
    return course


# ---------------- 课时 ----------------


async def get_lesson(db: AsyncSession, lesson_id: str) -> Lesson | None:
    row = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    return row.scalar_one_or_none()


async def list_lessons_by_course(
    db: AsyncSession,
    course_id: str,
    *,
    published_only: bool = True,
) -> list[Lesson]:
    """按 sort_order 升序返回 course 下所有 lesson.

    设计
    ----
    - ``published_only=True``（默认）：上层 GET /v1/courses/{id}/lessons 在课程未发布时
      应当先 404，所以这里仅在 service 层做"课程存在且发布"的二次校验，避免某些
      用例（如管理端预览）误用时漏放未发布课程的 lessons。
    - ``published_only=False``：admin 预览 / seed 流程需要看草稿 lesson。
    """

    if published_only:
        course = await get_course(db, course_id)
        if course is None or not course.is_published:
            return []
    rows = await db.execute(
        select(Lesson)
        .where(Lesson.course_id == course_id)
        .order_by(Lesson.sort_order.asc())
    )
    return list(rows.scalars().all())


async def create_lesson(db: AsyncSession, payload: LessonCreate) -> Lesson:
    course = await get_course(db, payload.course_id)
    if course is None:
        raise NotFoundError(code=40406, message="课程不存在")
    if course.is_published:
        raise BadRequestError(
            code=40903,
            message="已发布课程不允许新增 / 修改 lesson，请先下架",
        )
    if payload.drill_ids:
        await _validate_drill_ids(db, set(payload.drill_ids))

    lesson = Lesson(
        id=new_id("lsn"),
        course_id=payload.course_id,
        code=payload.code,
        title=payload.title,
        sort_order=payload.sort_order,
        duration_minutes=payload.duration_minutes,
        video_url=payload.video_url,
        transcript=payload.transcript,
        drill_ids=list(payload.drill_ids),
        pro_clip_ids=list(payload.pro_clip_ids),
        quiz_payload=payload.quiz_payload,
        pass_criteria=dict(payload.pass_criteria),
    )
    db.add(lesson)
    await db.flush()
    logger.info("lesson_created", lesson_id=lesson.id, course_id=lesson.course_id)
    return lesson


async def _validate_drill_ids(db: AsyncSession, drill_ids: set[str]) -> None:
    """检查 drill_ids 引用的所有 drill 都在 ``drills`` 表且 ``is_active=True``."""

    if not drill_ids:
        return
    found = await db.execute(
        select(Drill.id).where(Drill.id.in_(list(drill_ids)), Drill.is_active.is_(True))
    )
    found_ids = {row[0] for row in found.all()}
    missing = drill_ids - found_ids
    if missing:
        raise BadRequestError(
            code=40010,
            message="lesson 引用的 drill 不存在或未启用",
            detail=f"缺失：{','.join(sorted(missing))}",
        )


# ---------------- 进度状态机 ----------------


async def get_progress(
    db: AsyncSession, *, user_id: str, lesson_id: str
) -> UserCourseProgress | None:
    row = await db.execute(
        select(UserCourseProgress).where(
            UserCourseProgress.user_id == user_id,
            UserCourseProgress.lesson_id == lesson_id,
        )
    )
    return row.scalar_one_or_none()


async def upsert_progress(
    db: AsyncSession,
    *,
    user_id: str,
    lesson_id: str,
    payload: UserCourseProgressUpdate,
) -> UserCourseProgress:
    """按状态机推进 lesson 进度.

    - 任意"非法迁移"抛 ``BadRequestError``
    - ``in_progress -> in_progress`` 视为重试，``attempts`` 累加
    - 进入 ``passed`` 写 ``passed_at``
    """

    progress = await get_progress(db, user_id=user_id, lesson_id=lesson_id)
    is_new = progress is None
    if is_new:
        progress = UserCourseProgress(
            id=new_id("ucp"),
            user_id=user_id,
            lesson_id=lesson_id,
            status="not_started",
        )

    next_status = payload.status
    allowed = VALID_STATUS_TRANSITIONS.get(progress.status, frozenset())
    if next_status != progress.status and next_status not in allowed:
        raise BadRequestError(
            code=40903,
            message="非法的进度状态迁移",
            detail=f"{progress.status} → {next_status}",
        )

    # 状态推进副作用
    if next_status == COURSE_STATUS_IN_PROGRESS:
        progress.attempts = (progress.attempts or 0) + 1
    if next_status == COURSE_STATUS_PASSED and progress.status != COURSE_STATUS_PASSED:
        progress.passed_at = datetime.now(UTC)

    progress.status = next_status
    if payload.last_score is not None:
        progress.last_score = payload.last_score
    if payload.failed_reasons is not None:
        progress.failed_reasons = list(payload.failed_reasons)
    if payload.notes is not None:
        progress.notes = payload.notes

    if is_new:
        db.add(progress)
    await db.flush()
    logger.info(
        "progress_updated",
        user_id=user_id,
        lesson_id=lesson_id,
        status=progress.status,
        attempts=progress.attempts,
    )
    return progress


# ---------------- 升阶 + 证书 ----------------


async def is_course_passed(
    db: AsyncSession, *, user_id: str, course_id: str
) -> bool:
    """该 course 下所有 lesson 是否全部 passed."""

    total_q = await db.execute(
        select(func.count(Lesson.id)).where(Lesson.course_id == course_id)
    )
    total = int(total_q.scalar_one() or 0)
    if total == 0:
        return False
    passed_q = await db.execute(
        select(func.count(UserCourseProgress.id))
        .join(Lesson, Lesson.id == UserCourseProgress.lesson_id)
        .where(
            Lesson.course_id == course_id,
            UserCourseProgress.user_id == user_id,
            UserCourseProgress.status == COURSE_STATUS_PASSED,
        )
    )
    return int(passed_q.scalar_one() or 0) >= total


async def maybe_issue_certificate(
    db: AsyncSession, *, user_id: str, course_id: str
) -> CourseCertificate | None:
    """通关时落证书占位行（M11-05 异步合成 cert_url）。已发过则幂等。"""

    course = await get_course(db, course_id)
    if course is None:
        return None
    if not await is_course_passed(db, user_id=user_id, course_id=course_id):
        return None

    existing = await db.execute(
        select(CourseCertificate).where(
            CourseCertificate.user_id == user_id,
            CourseCertificate.course_id == course_id,
            CourseCertificate.revoked_at.is_(None),
        )
    )
    cert = existing.scalar_one_or_none()
    if cert is not None:
        return cert

    cert = CourseCertificate(
        id=new_id("crt"),
        user_id=user_id,
        course_id=course_id,
        stage=course.stage,
        cert_url=None,  # 由 M11-05 异步合成回填
    )
    db.add(cert)
    await db.flush()
    logger.info(
        "certificate_issued", cert_id=cert.id, user_id=user_id, course_id=course_id
    )
    return cert


async def seed_initial_courses(db: AsyncSession) -> list[Course]:
    """开发 / E2E 用：写入 stage 1 的 1 门示范课程 + 3 节 lesson，幂等.

    设计要点
    --------
    - **幂等**：用 ``courses.code`` 唯一约束做去重；已存在就直接 return existing。
    - **不引用 drills**：本 PR 故意把 ``drill_ids=[]`` 而不是塞 demo drill_id，因为
      drills 表是 seed 数据，写入时机不可控；若引用 drill 而 drill 不存在，
      ``publish_course`` 会校验失败 → 影响后续 E2E。
    - **stage 1 文案**：基础挥杆 1 + 站姿 / 握杆 / 上杆三个 lesson；M11-03 UI
      可以直接拉出来渲染端到端 demo。
    - 仅 1 门课、3 节 lesson：避免 PR 引入大块固定文本被 review；运营真正上线
      时通过专门的 admin 工具批量录入。
    """

    code = "stage1-basic-swing-v1"
    existing = await db.execute(select(Course).where(Course.code == code))
    course = existing.scalar_one_or_none()
    if course is not None:
        return [course]

    course = Course(
        id=new_id("crs"),
        code=code,
        title="基础挥杆 1：站姿与握杆",
        subtitle="第 1 阶 · 1/7 课",
        cover_url=None,
        stage=1,
        sort_order=1,
        is_member_only=False,
        description="从零开始的高尔夫挥杆。本课覆盖站姿、握杆与上杆基本姿态。",
        learning_objectives=[
            "理解中立握杆与重叠 / 互锁 / 棒球握法差异",
            "掌握肩 / 胯 / 脚的对齐与重心分布",
            "完成上杆顶点的初步定位",
        ],
        estimated_minutes=45,
        is_published=False,  # 先建草稿，加完 lesson 再 publish
    )
    db.add(course)
    await db.flush()

    lessons_spec: list[dict] = [
        {
            "code": "stage1-basic-swing-v1-l1",
            "title": "站姿与对齐",
            "sort_order": 1,
            "duration_minutes": 15,
            "video_url": None,
            "transcript": (
                "本节学习高尔夫的基本站姿：双脚与肩同宽、膝盖微屈、上身前倾，"
                "球的位置随杆型变化。重心 50/50 平均分布，避免前后偏移。"
            ),
            "pass_criteria": {"required_quiz_score": 70},
        },
        {
            "code": "stage1-basic-swing-v1-l2",
            "title": "握杆三种方式",
            "sort_order": 2,
            "duration_minutes": 15,
            "video_url": None,
            "transcript": (
                "中立握杆建议先用重叠或互锁握法，棒球握法仅推荐手部力量薄弱的初学者。"
                "握杆压力以 3-4 / 10 为佳，过紧会限制手腕铰链。"
            ),
            "pass_criteria": {"required_quiz_score": 70},
        },
        {
            "code": "stage1-basic-swing-v1-l3",
            "title": "上杆顶点定位",
            "sort_order": 3,
            "duration_minutes": 15,
            "video_url": None,
            "transcript": (
                "上杆顶点：左肩转到下颌下方，杆头指向目标线，左臂保持伸直但不僵硬。"
                "训练时可在镜子前练习定型；进入 M11-04 考核前完成至少 3 组定型练习。"
            ),
            "pass_criteria": {"required_quiz_score": 70},
        },
    ]
    for spec in lessons_spec:
        lesson = Lesson(
            id=new_id("lsn"),
            course_id=course.id,
            code=spec["code"],
            title=spec["title"],
            sort_order=spec["sort_order"],
            duration_minutes=spec["duration_minutes"],
            video_url=spec["video_url"],
            transcript=spec["transcript"],
            drill_ids=[],
            pro_clip_ids=[],
            quiz_payload=None,
            pass_criteria=spec["pass_criteria"],
        )
        db.add(lesson)
    await db.flush()

    # 一次性 publish；调用方负责 commit
    course.is_published = True
    course.published_at = datetime.now(UTC)
    await db.flush()
    logger.info("seed_initial_courses_done", course_id=course.id, lessons=len(lessons_spec))
    return [course]


async def current_user_stage(db: AsyncSession, user_id: str) -> int:
    """用户当前所处阶段：已通关 ``courses.stage`` 的最大值；未开始则返回 1。"""

    row = await db.execute(
        select(func.max(Course.stage))
        .join(CourseCertificate, CourseCertificate.course_id == Course.id)
        .where(
            CourseCertificate.user_id == user_id,
            CourseCertificate.revoked_at.is_(None),
        )
    )
    val = row.scalar_one_or_none()
    if val is None:
        return 1
    return min(MAX_STAGE, int(val) + 1)


__all__ = [
    "create_course",
    "create_lesson",
    "current_user_stage",
    "get_course",
    "get_lesson",
    "get_progress",
    "is_course_passed",
    "list_lessons_by_course",
    "list_published_courses",
    "maybe_issue_certificate",
    "publish_course",
    "seed_initial_courses",
    "upsert_progress",
]
