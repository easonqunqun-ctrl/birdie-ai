"""M11-01 course_service 单测（对齐 docs/23 §7.1 AC-2）.

覆盖
----
1. 创建课程 + 创建课时 + 发布课程（drills 引用校验）
2. 状态机：``not_started -> in_progress -> passed``；非法迁移抛 BadRequestError
3. ``is_course_passed`` 在所有 lesson 都 passed 时返回 True
4. ``maybe_issue_certificate`` 通关后落证书占位，重复触发幂等
5. ``current_user_stage`` 按已通关 course.stage 最大值 +1
6. 发布课程时 drill_ids 引用不存在的 drill → 拒绝
7. 已发布课程禁止新增 lesson
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError
from app.core.security import new_id
from app.models.course import (
    COURSE_STATUS_IN_PROGRESS,
    COURSE_STATUS_PASSED,
)
from app.models.training import Drill
from app.models.user import User
from app.schemas.course import (
    CourseCreate,
    LessonCreate,
    UserCourseProgressUpdate,
)
from app.services import course_service as svc


async def _make_user(db: AsyncSession) -> User:
    u = User(
        id=new_id("usr"),
        wechat_openid=f"o_{new_id('mock')}",
        nickname="t",
        invite_code=new_id("inv")[-6:].upper(),
    )
    db.add(u)
    await db.flush()
    return u


async def _make_drill(db: AsyncSession, idx: int = 0) -> Drill:
    d = Drill(
        id=f"drill_test_{idx}_{new_id('x')[-6:]}",
        name=f"test_drill_{idx}",
        description="for test",
        duration_minutes=10,
        difficulty="easy",
    )
    db.add(d)
    await db.flush()
    return d


@pytest.mark.asyncio
async def test_create_course_and_lesson_happy_path() -> None:
    async with AsyncSessionLocal() as db:
        drill = await _make_drill(db, 1)

        course = await svc.create_course(
            db,
            CourseCreate(
                code=f"stage_3_iron_basics_{new_id('x')[-6:]}",
                title="Stage 3 · Iron Basics",
                stage=3,
                learning_objectives=["建立标准站位"],
            ),
        )
        lesson = await svc.create_lesson(
            db,
            LessonCreate(
                course_id=course.id,
                code=f"lsn_iron_setup_{new_id('x')[-6:]}",
                title="Iron setup",
                sort_order=0,
                drill_ids=[drill.id],
                pass_criteria={"analysis_score_min": 75},
            ),
        )
        assert lesson.course_id == course.id
        assert lesson.drill_ids == [drill.id]

        published = await svc.publish_course(db, course.id)
        assert published.is_published is True


@pytest.mark.asyncio
async def test_publish_course_rejects_missing_drill() -> None:
    async with AsyncSessionLocal() as db:
        course = await svc.create_course(
            db,
            CourseCreate(
                code=f"stage_1_warmup_{new_id('x')[-6:]}",
                title="Warmup",
                stage=1,
            ),
        )
        # 走旁路插 lesson（drill_ids 引用不存在的 drill）
        from app.models.course import Lesson

        bad_lesson = Lesson(
            id=new_id("lsn"),
            course_id=course.id,
            code=f"lsn_bad_{new_id('x')[-6:]}",
            title="bad",
            sort_order=0,
            drill_ids=["drill_does_not_exist_xxx"],
        )
        db.add(bad_lesson)
        await db.flush()

        with pytest.raises(BadRequestError):
            await svc.publish_course(db, course.id)


@pytest.mark.asyncio
async def test_create_lesson_rejected_after_publish() -> None:
    async with AsyncSessionLocal() as db:
        drill = await _make_drill(db, 2)
        course = await svc.create_course(
            db,
            CourseCreate(
                code=f"stage_2_x_{new_id('x')[-6:]}",
                title="P",
                stage=2,
            ),
        )
        await svc.create_lesson(
            db,
            LessonCreate(
                course_id=course.id,
                code=f"l1_{new_id('x')[-6:]}",
                title="L1",
                sort_order=0,
                drill_ids=[drill.id],
            ),
        )
        await svc.publish_course(db, course.id)

        with pytest.raises(BadRequestError):
            await svc.create_lesson(
                db,
                LessonCreate(
                    course_id=course.id,
                    code=f"l2_{new_id('x')[-6:]}",
                    title="L2",
                    sort_order=1,
                ),
            )


@pytest.mark.asyncio
async def test_progress_state_machine_happy() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        drill = await _make_drill(db, 3)
        course = await svc.create_course(
            db,
            CourseCreate(
                code=f"c_{new_id('x')[-6:]}",
                title="C",
                stage=1,
            ),
        )
        lesson = await svc.create_lesson(
            db,
            LessonCreate(
                course_id=course.id,
                code=f"l_{new_id('x')[-6:]}",
                title="L",
                sort_order=0,
                drill_ids=[drill.id],
            ),
        )
        # not_started -> in_progress
        p1 = await svc.upsert_progress(
            db,
            user_id=u.id,
            lesson_id=lesson.id,
            payload=UserCourseProgressUpdate(status=COURSE_STATUS_IN_PROGRESS),
        )
        assert p1.status == COURSE_STATUS_IN_PROGRESS
        assert p1.attempts == 1

        # in_progress -> passed
        p2 = await svc.upsert_progress(
            db,
            user_id=u.id,
            lesson_id=lesson.id,
            payload=UserCourseProgressUpdate(
                status=COURSE_STATUS_PASSED, last_score=88
            ),
        )
        assert p2.status == COURSE_STATUS_PASSED
        assert p2.last_score == 88
        assert p2.passed_at is not None


@pytest.mark.asyncio
async def test_progress_illegal_transition_rejected() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        drill = await _make_drill(db, 4)
        course = await svc.create_course(
            db,
            CourseCreate(code=f"c_{new_id('x')[-6:]}", title="C", stage=1),
        )
        lesson = await svc.create_lesson(
            db,
            LessonCreate(
                course_id=course.id,
                code=f"l_{new_id('x')[-6:]}",
                title="L",
                sort_order=0,
                drill_ids=[drill.id],
            ),
        )
        # not_started -> passed 非法
        with pytest.raises(BadRequestError):
            await svc.upsert_progress(
                db,
                user_id=u.id,
                lesson_id=lesson.id,
                payload=UserCourseProgressUpdate(status=COURSE_STATUS_PASSED),
            )


@pytest.mark.asyncio
async def test_certificate_idempotent_on_pass() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        drill = await _make_drill(db, 5)
        course = await svc.create_course(
            db,
            CourseCreate(code=f"c_{new_id('x')[-6:]}", title="C", stage=2),
        )
        lesson = await svc.create_lesson(
            db,
            LessonCreate(
                course_id=course.id,
                code=f"l_{new_id('x')[-6:]}",
                title="L",
                sort_order=0,
                drill_ids=[drill.id],
            ),
        )
        await svc.upsert_progress(
            db,
            user_id=u.id,
            lesson_id=lesson.id,
            payload=UserCourseProgressUpdate(status=COURSE_STATUS_IN_PROGRESS),
        )
        await svc.upsert_progress(
            db,
            user_id=u.id,
            lesson_id=lesson.id,
            payload=UserCourseProgressUpdate(status=COURSE_STATUS_PASSED),
        )

        c1 = await svc.maybe_issue_certificate(db, user_id=u.id, course_id=course.id)
        c2 = await svc.maybe_issue_certificate(db, user_id=u.id, course_id=course.id)
        assert c1 is not None
        assert c2 is not None
        assert c1.id == c2.id  # 幂等
        assert c1.stage == 2

        stage = await svc.current_user_stage(db, u.id)
        # 通关 stage=2 → 当前阶段 3
        assert stage == 3
