"""训练计划 / 打卡业务逻辑（W7-T3）.

核心场景：
1. **分析完成 → 生成/更新当周训练计划**：
   `generate_or_update_weekly(db, user_id, analysis_id, issues)` 被
   `app.tasks.analysis_tasks._mark_completed` 在完成分支调用。

   策略：
   - 以"当周周一"为 key 做 upsert（`uq_user_week`）；同一周多次分析会**增量追加**
     新 issue 对应的任务，而不是重建 plan
   - 任务在"本周余下天数 + 今天"里做轮询分布（最少 3 天/最多 5 天），
     同一 drill_id 在同一 plan 里只出现一次

2. **用户打卡**：
   `complete_task(db, task_id, user, payload)` 写 `practice_logs` + 标记任务完成 +
   更新 plan.completed_tasks + 更新 `users.current_streak_days` / `last_practice_date` /
   `max_streak_days`（连续天数：今天已经打过 → 不叠；昨天 → +1；更早 → 重置为 1）。

3. **读计划**：`get_current_week_plan` / `list_practice_logs`（为 W8 进步曲线预留）。
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.security import new_id
from app.models.analysis import AnalysisIssue, SwingAnalysis
from app.models.training import Drill, PracticeLog, TrainingPlan, TrainingTask
from app.models.user import User
from app.schemas.training import TrainingTaskItem

# 每次分析至多生成几个任务（issues 去重后截断）
MAX_TASKS_PER_ANALYSIS = 5

log = logging.getLogger(__name__)


def training_task_to_item(
    task: TrainingTask,
    *,
    pro_clip_id: str | None = None,
    pro_player_name: str | None = None,
    pro_clip_unavailable: bool = False,
) -> TrainingTaskItem:
    """ORM → Pydantic；非法 `status` 降级，避免 model_validate 抛错导致 HTTP 500。"""
    raw = task.status or ""
    status: Literal["pending", "completed"] = "completed" if raw == "completed" else "pending"
    if raw not in ("pending", "completed"):
        log.warning(
            "invalid_training_task_status_coerced",
            extra={"task_id": task.id, "raw_status": raw},
        )
    task_kind: Literal["standard", "pro_clip_try_it"] = (
        "pro_clip_try_it" if pro_clip_id else "standard"
    )
    return TrainingTaskItem(
        id=task.id,
        plan_id=task.plan_id,
        drill_id=task.drill_id,
        scheduled_date=task.scheduled_date,
        sort_order=int(task.sort_order or 0),
        status=status,
        completed_at=task.completed_at,
        verification_analysis_id=task.verification_analysis_id,
        task_kind=task_kind,
        pro_clip_id=pro_clip_id,
        pro_player_name=pro_player_name,
        pro_clip_unavailable=pro_clip_unavailable,
    )


# ============================================================
# 周边界工具
# ============================================================
def _china_today() -> date:
    """用 UTC+8 切日。streak / scheduled_date 都基于"北京日"."""
    return (datetime.now(UTC) + timedelta(hours=8)).date()


def week_bounds(d: date) -> tuple[date, date]:
    """返回 d 所在周的周一 / 周日."""
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


# ============================================================
# drill 选择
# ============================================================
async def _resolve_drill_ids_for_issues(
    db: AsyncSession,
    issues: list[dict],
) -> list[str]:
    """给定 issue list（[{type, severity, ...}]），挑选对应 drill_id，按严重度排序并去重。

    优先使用 `drills.target_issues @> [<type>]` 查询；若找不到任何匹配，
    回退到 ai_engine 静态表（但实际运行时数据库里 drills 表是 seed 好的，
    几乎不会走到兜底）。
    """
    # severity 权重：轻→1，中→2，重→3；同 issue 多次出现取最高
    sev_weight = {"high": 3, "medium": 2, "low": 1}

    # 按 severity 排序（高→低）
    def _key(it: dict) -> int:
        return -sev_weight.get(it.get("severity", "low"), 1)

    sorted_issues = sorted(issues, key=_key)

    picked: list[str] = []
    seen: set[str] = set()

    for issue in sorted_issues:
        issue_type = issue.get("type")
        if not issue_type:
            continue
        stmt = (
            select(Drill.id)
            .where(
                Drill.is_active.is_(True),
                Drill.target_issues.contains([issue_type]),
            )
            .order_by(Drill.sort_order)
        )
        rows = (await db.execute(stmt)).scalars().all()
        for drill_id in rows:
            if drill_id in seen:
                continue
            seen.add(drill_id)
            picked.append(drill_id)
            break  # 同一个 issue 只取一个 drill，避免 plan 被一个问题填满

        if len(picked) >= MAX_TASKS_PER_ANALYSIS:
            break

    return picked


# ============================================================
# 生成 / 更新当周训练计划
# ============================================================
async def generate_or_update_weekly(
    db: AsyncSession,
    user_id: str,
    analysis_id: str,
    issues: list[dict],
) -> TrainingPlan | None:
    """分析完成后同步调用：把 issues → drills → 本周训练任务。

    - 无 issue → 不创建 plan（返回 None）。
    - 本周已有 plan → 追加缺失 drill 的任务（不重建）。
    - 本周没有 plan → 新建 + 生成任务。
    任务日期分布：从今天开始按顺序每天一个；若当周剩余天数少于任务数，则从今天起循环到下周一（不跨周）。
    """
    drill_ids = await _resolve_drill_ids_for_issues(db, issues)
    if not drill_ids:
        return None

    today = _china_today()
    monday, sunday = week_bounds(today)

    # 查本周是否已有 plan
    stmt = (
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.tasks))
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.week_start == monday,
        )
    )
    plan = (await db.execute(stmt)).scalar_one_or_none()

    if plan is None:
        # 并发「本周首次建计划」可能同时 INSERT，触发 uq_user_week → IntegrityError
        candidate = TrainingPlan(
            id=new_id("plan"),
            user_id=user_id,
            week_start=monday,
            week_end=sunday,
            source_analysis_id=analysis_id,
            total_tasks=0,
            completed_tasks=0,
        )
        db.add(candidate)
        try:
            async with db.begin_nested():
                await db.flush()
        except IntegrityError:
            plan = (await db.execute(stmt)).scalar_one_or_none()
            if plan is None:
                raise
        else:
            plan = candidate

    existing_drill_ids = {t.drill_id for t in plan.tasks}
    existing_count = len(plan.tasks)
    plan.source_analysis_id = analysis_id

    new_drills = [d for d in drill_ids if d not in existing_drill_ids]
    if not new_drills:
        return plan

    # 安排日期：从今天起每天一个，塞到周日为止；若任务数 > 剩余天数，则多余任务挤到周日
    remaining_days = (sunday - today).days + 1  # 包含今天
    for offset, drill_id in enumerate(new_drills):
        day_offset = min(offset, remaining_days - 1)
        scheduled = today + timedelta(days=day_offset)
        db.add(
            TrainingTask(
                id=new_id("task"),
                plan_id=plan.id,
                user_id=user_id,
                drill_id=drill_id,
                scheduled_date=scheduled,
                sort_order=existing_count + offset,
                status="pending",
            )
        )

    plan.total_tasks = existing_count + len(new_drills)
    await db.flush()
    return plan


# ============================================================
# 打卡
# ============================================================
def _update_streak(user: User, today: date) -> None:
    """根据 last_practice_date 更新 current_streak_days / max_streak_days / last_practice_date."""
    last = user.last_practice_date
    if last is None:
        user.current_streak_days = 1
    elif last == today:
        # 今天已打过 → 不叠
        pass
    elif last == today - timedelta(days=1):
        user.current_streak_days = (user.current_streak_days or 0) + 1
    else:
        # 断了，重置
        user.current_streak_days = 1

    user.last_practice_date = today
    if user.current_streak_days > (user.max_streak_days or 0):
        user.max_streak_days = user.current_streak_days


async def complete_task(
    db: AsyncSession,
    task_id: str,
    user: User,
    *,
    duration_minutes: int | None = None,
    notes: str | None = None,
) -> tuple[TrainingTask, TrainingPlan]:
    """打卡：
    1. 校验 task 归属 + 状态
    2. 写 practice_log
    3. 置 task.status=completed + plan.completed_tasks++
    4. 更新 user streak
    """
    task = await db.get(TrainingTask, task_id)
    if task is None:
        raise NotFoundError(code=40401, message="任务不存在")
    if task.user_id != user.id:
        raise ForbiddenError(code=40302, message="无权操作此任务")
    if task.status == "completed":
        raise BadRequestError(code=40014, message="任务已完成，无需重复打卡")

    today = _china_today()
    now = datetime.now(UTC)

    task.status = "completed"
    task.completed_at = now

    db.add(
        PracticeLog(
            id=new_id("plog"),
            user_id=user.id,
            task_id=task.id,
            drill_id=task.drill_id,
            practice_date=today,
            duration_minutes=duration_minutes,
            notes=notes,
        )
    )

    plan = await db.get(TrainingPlan, task.plan_id)
    if plan is None:
        raise NotFoundError(code=40401, message="训练计划不存在")  # defensive
    plan.completed_tasks = (plan.completed_tasks or 0) + 1

    _update_streak(user, today)

    await db.flush()
    return task, plan


# ============================================================
# 查询
# ============================================================
async def get_current_week_plan(db: AsyncSession, user: User) -> TrainingPlan | None:
    """取当周 plan（含 tasks）。没有就返回 None，由 API 层决定是否 404。"""
    monday, _ = week_bounds(_china_today())
    stmt = (
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.tasks))
        .where(
            TrainingPlan.user_id == user.id,
            TrainingPlan.week_start == monday,
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def ensure_current_week_plan(db: AsyncSession, user_id: str) -> TrainingPlan:
    """确保当周训练计划存在（无 issue 也可建空 plan，供 pro try-it 等追加任务）."""

    today = _china_today()
    monday, sunday = week_bounds(today)

    stmt = (
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.tasks))
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.week_start == monday,
        )
    )
    plan = (await db.execute(stmt)).scalar_one_or_none()
    if plan is not None:
        return plan

    candidate = TrainingPlan(
        id=new_id("plan"),
        user_id=user_id,
        week_start=monday,
        week_end=sunday,
        source_analysis_id=None,
        total_tasks=0,
        completed_tasks=0,
    )
    db.add(candidate)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        plan = (await db.execute(stmt)).scalar_one_or_none()
        if plan is None:
            raise
    else:
        plan = candidate
    return plan


async def add_analysis_to_weekly_plan(
    db: AsyncSession,
    *,
    analysis_id: str,
    user: User,
) -> TrainingPlan:
    """报告页 / 教练页「加入训练计划」后端入口（W8 闭环补齐）。

    把指定分析的 issues 同步生成/更新到当周训练计划，复用
    `generate_or_update_weekly` 的 upsert 语义：
      - 同一周内多次调用幂等（同 drill 不重复加任务）。
      - 旧分析、本周已存在 plan 的场景下，新增任务追加到现有 plan 上。

    错误：
      - analysis 不存在 → NotFoundError(40402)
      - 不是当前用户的分析 → ForbiddenError(40302)
      - 分析未完成（无 issues）→ BadRequestError(40015)
      - issues 全部无对应 drill → BadRequestError(40016)（应该极少发生）

    返回最新 plan（含 tasks），由 API 层包成 TrainingPlanDetail。
    `sample` 这种伪 ID 由 API 层挡掉，本函数不处理。
    """
    analysis = await db.get(SwingAnalysis, analysis_id)
    if analysis is None:
        raise NotFoundError(code=40402, message="分析报告不存在")
    if analysis.deleted_at is not None:
        raise NotFoundError(code=40402, message="分析报告不存在")
    if analysis.user_id != user.id:
        raise ForbiddenError(code=40302, message="无权操作此分析")
    if analysis.status != "completed":
        raise BadRequestError(
            code=40015, message="分析尚未完成，暂时无法生成训练计划"
        )

    # 把 AnalysisIssue ORM 对象转成 generate_or_update_weekly 期望的 dict 列表
    issues_stmt = (
        select(AnalysisIssue)
        .where(AnalysisIssue.analysis_id == analysis.id)
        .order_by(AnalysisIssue.sort_order)
    )
    issue_rows = list((await db.execute(issues_stmt)).scalars().all())
    issues_dicts = [
        {"type": it.issue_type, "severity": it.severity}
        for it in issue_rows
    ]
    if not issues_dicts:
        # 一次"完美"挥杆的兜底：没有 issue → 没有要练的动作；前端按 NOOP 处理
        raise BadRequestError(
            code=40015, message="本次分析没有需要重点练习的问题"
        )

    plan = await generate_or_update_weekly(
        db, user.id, analysis.id, issues_dicts
    )
    if plan is None:
        # 极少：所有 issue 都无匹配 drill（drills seed 缺失等）
        raise BadRequestError(
            code=40016, message="暂无对应训练动作，请稍后重试"
        )

    # 重新拉一次带 tasks 的 plan，确保 selectinload 生效（generate_or_update_weekly
    # 内部 add 后没有 refresh tasks 关系）
    refreshed_stmt = (
        select(TrainingPlan)
        .options(selectinload(TrainingPlan.tasks))
        .where(TrainingPlan.id == plan.id)
    )
    refreshed = (await db.execute(refreshed_stmt)).scalar_one()
    return refreshed


async def list_practice_logs_for_month(
    db: AsyncSession,
    user: User,
    month: str,  # "YYYY-MM"
) -> list[PracticeLog]:
    """查某月的打卡日志。month 格式 "YYYY-MM"。"""
    try:
        year, mon = month.split("-")
        start = date(int(year), int(mon), 1)
    except (ValueError, IndexError) as e:
        raise BadRequestError(code=40001, message=f"month 参数格式应为 YYYY-MM：{month}") from e

    end = (
        date(int(year) + 1, 1, 1)
        if mon == "12"
        else date(int(year), int(mon) + 1, 1)
    )

    stmt = (
        select(PracticeLog)
        .where(
            PracticeLog.user_id == user.id,
            PracticeLog.practice_date >= start,
            PracticeLog.practice_date < end,
        )
        .order_by(PracticeLog.practice_date.desc(), PracticeLog.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def list_drills(db: AsyncSession) -> list[Drill]:
    stmt = select(Drill).where(Drill.is_active.is_(True)).order_by(Drill.sort_order)
    return list((await db.execute(stmt)).scalars().all())
