"""挥杆分析 Celery 任务。

整体流程（对应 docs/12-M2任务拆分.md T2）：

    ┌───────────────────────────┐
    │ create_analysis           │
    │   └─ _dispatch_analysis_task(analysis_id)  ── delay() ──┐
    └───────────────────────────┘                             │
                                                              ▼
                                          ┌──────────────────────────────────┐
                                          │ run_swing_analysis (celery)      │
                                          │   │                               │
                                          │   ▼                               │
                                          │ _run_swing_analysis_async         │
                                          │   1. 置 processing                │
                                          │   2. 调 ai_engine（重试 ≤ 3 次） │
                                          │   3a. completed → 落库报告        │
                                          │   3b. engine status=failed        │
                                          │       → 落库 failed + 退配额      │
                                          │   3c. engine 超时                 │
                                          │       → 终态 failed + 退配额      │
                                          └──────────────────────────────────┘

关键实现选择：
- Celery task body 用 **独立线程 + asyncio.run()** 运行 async 内核；
  这样即便 celery `task_always_eager=True` 模式下从 FastAPI 的 running loop 发起，
  也不会撞到 "asyncio.run cannot be called from a running event loop"。
  生产 worker 是独立 python 进程，同样适用。
- 每次任务内部**新建 AsyncSession**，与当前事件循环绑定；不复用 FastAPI 请求期的 session。
- 重试：由本模块**手动**做，Celery 层只跑一次。测试里可通过
  `monkeypatch _run_swing_analysis_async` 或 `AIEngineClient.analyze` 精准控制。
"""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.integrations.ai_engine import get_ai_engine
from app.models.analysis import AnalysisIssue, AnalysisRecommendation, SwingAnalysis
from app.services import quota_service

log = structlog.get_logger("tasks.analysis")

# AI Engine 可达性重试：首次失败后最多再尝试 2 次（共 3 次），指数退避 1s / 2s
MAX_AI_ENGINE_RETRIES = 2
RETRY_BACKOFF_BASE_SECONDS = 1


# =====================================================================
# Celery 入口
# =====================================================================
@celery_app.task(name="xiaoniao.run_swing_analysis", bind=True)
def run_swing_analysis(self, analysis_id: str) -> None:
    """同步 shim：把 async 内核放在独立线程里跑，避开 event loop 冲突。"""
    _run_coro_in_thread(_run_swing_analysis_async(analysis_id))


def _run_coro_in_thread(coro) -> Any:
    result: list = []
    exc: list[BaseException] = []

    def _target() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as e:
            exc.append(e)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join()
    if exc:
        raise exc[0]
    return result[0] if result else None


# =====================================================================
# Async 内核
# =====================================================================
async def _run_swing_analysis_async(analysis_id: str) -> None:
    """T2 主流程：走一条 analysis 从 pending → completed/failed 的状态机。

    幂等：进入时若 analysis 已 terminal（completed / failed），直接返回，不重做。
    """
    # 1) 置 processing + 预加载 user_id / video_url
    meta = await _mark_processing(analysis_id)
    if meta is None:
        log.info("analysis_already_terminal_skip", analysis_id=analysis_id)
        return

    # 2) 调 ai_engine，带重试
    engine_result: dict | None = None
    last_exc: Exception | None = None
    for attempt in range(MAX_AI_ENGINE_RETRIES + 1):
        try:
            client = get_ai_engine()
            engine_result = await client.analyze(
                analysis_id=analysis_id,
                video_url=meta["video_url"],
                camera_angle=meta["camera_angle"],
                club_type=meta["club_type"],
            )
            break
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
            last_exc = e
            log.warning(
                "ai_engine_retry",
                analysis_id=analysis_id,
                attempt=attempt,
                err=repr(e),
            )
            if attempt < MAX_AI_ENGINE_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF_BASE_SECONDS * (2**attempt))

    if engine_result is None:
        # 终态失败：AI Engine 网络级不可达
        await _mark_failed(
            analysis_id,
            error_code=50104,
            error_message=f"AI 引擎不可达: {type(last_exc).__name__}",
            refund=True,
        )
        return

    # 3) ai_engine 明确返回 failed（画质差、未检测到人体等）
    if engine_result.get("status") == "failed":
        await _mark_failed(
            analysis_id,
            error_code=engine_result.get("error_code") or 50101,
            error_message=engine_result.get("error_message") or "分析失败",
            refund=True,
        )
        return

    # 4) 正常落库
    await _mark_completed(analysis_id, engine_result)


# =====================================================================
# 状态写入辅助
# =====================================================================
async def _mark_processing(analysis_id: str) -> dict | None:
    """置 processing 并返回后续环节需要的字段；若已 terminal 则返回 None。"""
    async with AsyncSessionLocal() as db:
        analysis = await db.get(SwingAnalysis, analysis_id)
        if analysis is None:
            log.warning("analysis_not_found", analysis_id=analysis_id)
            return None
        if analysis.status in {"completed", "failed"}:
            return None
        analysis.status = "processing"
        analysis.stage = "preprocessing"
        analysis.stage_progress = 10
        await db.commit()
        return {
            "user_id": analysis.user_id,
            "video_url": analysis.video_url,
            "camera_angle": analysis.camera_angle,
            "club_type": analysis.club_type,
            "created_at": analysis.created_at,
        }


async def _mark_failed(
    analysis_id: str,
    *,
    error_code: int,
    error_message: str,
    refund: bool,
) -> None:
    """置 failed + 可选退配额（保证幂等）."""
    async with AsyncSessionLocal() as db:
        analysis = await db.get(SwingAnalysis, analysis_id)
        if analysis is None or analysis.status in {"completed", "failed"}:
            return
        analysis.status = "failed"
        analysis.stage = None
        analysis.stage_progress = 0
        analysis.error_code = error_code
        analysis.error_message = error_message[:500]
        if refund and not analysis.quota_refunded:
            # 按 analysis.created_at 所在的月份（UTC+8）退回该月的配额
            created_at_local = (analysis.created_at or datetime.now(UTC)) + timedelta(hours=8)
            quota_month = created_at_local.strftime("%Y-%m")
            refunded = await quota_service.refund_analysis_quota_by_user_month(
                db, user_id=analysis.user_id, quota_month=quota_month
            )
            analysis.quota_refunded = refunded
        await db.commit()


async def _mark_completed(analysis_id: str, engine_result: dict) -> None:
    """把 ai_engine 返回的 AnalyzeResult 落到 swing_analyses + 子表。"""
    async with AsyncSessionLocal() as db:
        stmt = (
            select(SwingAnalysis)
            .options(
                selectinload(SwingAnalysis.issues),
                selectinload(SwingAnalysis.recommendations),
            )
            .where(SwingAnalysis.id == analysis_id)
        )
        analysis = (await db.execute(stmt)).scalar_one_or_none()
        if analysis is None or analysis.status in {"completed", "failed"}:
            return

        # 主记录
        analysis.status = "completed"
        analysis.stage = None
        analysis.stage_progress = 100
        analysis.overall_score = engine_result.get("overall_score")
        analysis.phase_scores = _dump_phase_scores(engine_result.get("phase_scores"))
        analysis.phase_timestamps = _dump_phase_timestamps(engine_result.get("phase_timestamps"))
        analysis.skeleton_video_url = engine_result.get("skeleton_video_url")
        analysis.skeleton_data_url = engine_result.get("skeleton_data_url")
        analysis.thumbnail_url = engine_result.get("thumbnail_url")
        analysis.analyzed_at = datetime.now(UTC)

        # 清掉旧子记录（幂等：重跑任务时不累加）
        for it in list(analysis.issues):
            await db.delete(it)
        for r in list(analysis.recommendations):
            await db.delete(r)
        await db.flush()

        # issues
        for idx, it in enumerate(engine_result.get("issues") or []):
            ts = it.get("key_frame_timestamp")
            db.add(
                AnalysisIssue(
                    id=new_id("iss"),
                    analysis_id=analysis.id,
                    issue_type=it["type"],
                    name=it["name"],
                    severity=it["severity"],
                    description=it["description"],
                    key_frame_url=it.get("key_frame_url"),
                    key_frame_timestamp=ts,
                    sort_order=idx,
                )
            )
        # recommendations
        for idx, r in enumerate(engine_result.get("recommendations") or []):
            db.add(
                AnalysisRecommendation(
                    id=new_id("rec"),
                    analysis_id=analysis.id,
                    drill_id=r["drill_id"],
                    target_issue=r.get("target_issue"),
                    sort_order=idx,
                )
            )

        await db.commit()


# =====================================================================
# dict 规整（把 ai_engine Pydantic 模型序列化后的结构装入 JSONB）
# =====================================================================
def _dump_phase_scores(raw: dict | None) -> dict | None:
    if raw is None:
        return None
    return {
        k: {
            "score": int(v["score"]),
            "label": v["label"],
            "is_weakest": bool(v.get("is_weakest", False)),
        }
        for k, v in raw.items()
    }


def _dump_phase_timestamps(raw: dict | None) -> dict | None:
    if raw is None:
        return None
    # ai_engine 用 {"start": x, "end": y}；后端 schema 也是 {"start", "end"}。
    return {
        k: {"start": float(v["start"]), "end": float(v["end"])}
        for k, v in raw.items()
    }


__all__ = [
    "MAX_AI_ENGINE_RETRIES",
    "RETRY_BACKOFF_BASE_SECONDS",
    "_run_swing_analysis_async",
    "run_swing_analysis",
]
