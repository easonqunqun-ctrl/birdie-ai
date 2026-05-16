"""训练计划 / 打卡 API（W7-T3）.

端点概览（对齐 docs/02 §五 训练计划接口）：

- `GET  /v1/me/training-plan/current`            取本周训练计划（若无则返回 null）
- `POST /v1/training-plan/tasks/{task_id}/complete`  打卡
- `GET  /v1/me/practice-logs?month=YYYY-MM`      月度练习记录（给 W8 进步曲线预留）
- `GET  /v1/drills`                              动作库（前端内置兜底，此接口便于后续替换）
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.training import (
    CompleteTaskRequest,
    CompleteTaskResponse,
    DrillDetail,
    PracticeLogItem,
    TrainingPlanDetail,
)
from app.services import training_service

router = APIRouter()
me_router = APIRouter()


# ==================== /me/training-plan/current ====================
@me_router.get(
    "/training-plan/current",
    summary="取本周训练计划（含任务 + 完成度）；无则返回 null",
    response_model=APIResponse[TrainingPlanDetail | None],
)
async def get_current_plan(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[TrainingPlanDetail | None]:
    plan = await training_service.get_current_week_plan(db, user)
    if plan is None:
        return ok(None)
    # tasks 已经通过 selectinload 加载
    tasks = sorted(plan.tasks, key=lambda t: (t.scheduled_date, t.sort_order))
    detail = TrainingPlanDetail(
        id=plan.id,
        user_id=plan.user_id,
        week_start=plan.week_start,
        week_end=plan.week_end,
        source_analysis_id=plan.source_analysis_id,
        ai_summary=plan.ai_summary,
        total_tasks=plan.total_tasks,
        completed_tasks=plan.completed_tasks,
        tasks=[training_service.training_task_to_item(t) for t in tasks],
        created_at=plan.created_at,
    )
    return ok(detail)


# ==================== /training-plan/from-analysis/{analysis_id} ====================
@router.post(
    "/from-analysis/{analysis_id}",
    summary="把一份分析报告的问题加入当周训练计划（幂等）",
    description=(
        "对同一 analysis 多次调用是幂等的：相同 drill 不重复加任务。\n"
        "已成立的当周计划会被 **追加** 新任务，旧任务保留打卡状态。\n"
        "对 `sample` 等示例 ID 直接 400。"
    ),
    response_model=APIResponse[TrainingPlanDetail],
)
async def add_to_plan_from_analysis(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[TrainingPlanDetail]:
    from app.core.exceptions import BadRequestError

    if analysis_id == "sample" or not analysis_id:
        raise BadRequestError(code=40015, message="示例报告无法加入训练计划")

    plan = await training_service.add_analysis_to_weekly_plan(
        db, analysis_id=analysis_id, user=user
    )
    await db.commit()
    # plan.tasks 已经在 service 内 selectinload，无需再 refresh
    tasks = sorted(plan.tasks, key=lambda t: (t.scheduled_date, t.sort_order))
    detail = TrainingPlanDetail(
        id=plan.id,
        user_id=plan.user_id,
        week_start=plan.week_start,
        week_end=plan.week_end,
        source_analysis_id=plan.source_analysis_id,
        ai_summary=plan.ai_summary,
        total_tasks=plan.total_tasks,
        completed_tasks=plan.completed_tasks,
        tasks=[training_service.training_task_to_item(t) for t in tasks],
        created_at=plan.created_at,
    )
    return ok(detail)


# ==================== /training-plan/tasks/{task_id}/complete ====================
@router.post(
    "/tasks/{task_id}/complete",
    summary="打卡完成训练任务",
    response_model=APIResponse[CompleteTaskResponse],
)
async def complete_task(
    task_id: str,
    payload: CompleteTaskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[CompleteTaskResponse]:
    task, plan = await training_service.complete_task(
        db,
        task_id,
        user,
        duration_minutes=payload.duration_minutes,
        notes=payload.notes,
    )
    await db.commit()
    await db.refresh(task)
    await db.refresh(plan)
    await db.refresh(user)

    return ok(
        CompleteTaskResponse(
            task=training_service.training_task_to_item(task),
            current_streak_days=user.current_streak_days or 0,
            plan_completed_tasks=plan.completed_tasks,
            plan_total_tasks=plan.total_tasks,
        )
    )


# ==================== /me/practice-logs ====================
@me_router.get(
    "/practice-logs",
    summary="月度练习记录",
    response_model=APIResponse[list[PracticeLogItem]],
)
async def list_my_practice_logs(
    month: Annotated[str, Query(description="YYYY-MM，如 2026-04")],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[PracticeLogItem]]:
    logs = await training_service.list_practice_logs_for_month(db, user, month)
    return ok([PracticeLogItem.model_validate(lg) for lg in logs])


# ==================== /drills ====================
drills_router = APIRouter()


@drills_router.get(
    "",
    summary="动作库列表（前端可作为兜底数据源）",
    response_model=APIResponse[list[DrillDetail]],
)
async def list_drills(
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[DrillDetail]]:
    drills = await training_service.list_drills(db)
    return ok([DrillDetail.model_validate(d) for d in drills])
