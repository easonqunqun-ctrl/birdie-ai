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
import contextlib
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.core.database import engine as _shared_async_engine
from app.core.security import new_id
from app.integrations.ai_engine import get_ai_engine
from app.integrations.wechat_subscribe_message import send_analysis_completed_notification
from app.models.analysis import AnalysisIssue, AnalysisRecommendation, SwingAnalysis
from app.models.user import User
from app.schemas.analysis import SWING_STAGE_TIMELINE as STAGE_PROGRESSION
from app.services import invitation_service, quota_service, training_service

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
    """在独立线程里跑一个 async coro。

    每次都用 `asyncio.run` 创建全新 event loop。
    **关键**：用 wrapper 在 coro 执行前后调用 `engine.dispose()`：
      - 进入前 dispose：清掉上次 task 残留在 pool 里的、绑定到旧 loop 的 connection；
        否则下次 task 进来时第一次 acquire 会撞 "Future attached to a different loop"。
      - 退出前 dispose：避免 worker idle 期间 pool 持有一堆 stale conn。
    若不做这步，celery prefork worker 在第二次 task 起 100% 复现 asyncpg loop 错乱。
    """
    result: list = []
    exc: list[BaseException] = []

    async def _wrapped() -> Any:
        # 让 pool 在当前 loop 重建（首次跑时 pool 还空，dispose 是 no-op，零代价）
        await _shared_async_engine.dispose()
        try:
            return await coro
        finally:
            # 任务结束清空 pool；下次 task 拿到的依旧是属于当时 loop 的全新 conn
            with contextlib.suppress(Exception):
                await _shared_async_engine.dispose()

    def _target() -> None:
        try:
            result.append(asyncio.run(_wrapped()))
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

    # 2) 启动 stage 推进后台任务（让 waiting 页能看到 stage 变化）
    # 注意：仅在第一次尝试时启动；重试期间 stage 已经停在最后推进到的位置，
    # 重新启动反而会让 UI 上的进度往回跳。
    stage_task = asyncio.create_task(_progress_stages_loop(analysis_id))

    # 3) 调 ai_engine，带重试
    engine_result: dict | None = None
    last_exc: Exception | None = None
    try:
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
    finally:
        # 不论成功/失败，都把 stage 推进 task 收掉
        # cancel 期间任何异常都吞掉：stage 推进只是"装饰"，不应影响主流程
        stage_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await stage_task

    if engine_result is None:
        # 终态失败：AI Engine 网络级不可达（transport 错误，非业务错误）
        # W6-T6：改用 50100 表示后端 → ai_engine 通道失败；
        # 50101-50105 严格保留给 ai_engine 业务错误（见 docs/02 §1.4）
        await _mark_failed(
            analysis_id,
            error_code=50100,
            error_message=f"AI 引擎不可达: {type(last_exc).__name__}",
            refund=True,
        )
        return

    # 3) ai_engine 明确返回 failed（画质差、未检测到人体等）
    # 错误码透传策略：
    # - ai_engine 在 50101-50105 段返回业务错误码（见 ai_engine/app/errors.py）
    # - backend 直接透传到 swing_analyses.error_code，不做"翻译"——前端按 docs/02 §1.4
    #   看到的就是同一个码段
    # - 50101-50105 全部都退配额（用户没消费成功）
    # - 不在 50101-50105 段的码（理论上不应该出现）按 50100 兜底，仍退配额
    if engine_result.get("status") == "failed":
        raw_code = engine_result.get("error_code")
        error_code = raw_code if isinstance(raw_code, int) and 50100 <= raw_code <= 50199 else 50100
        await _mark_failed(
            analysis_id,
            error_code=error_code,
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


async def _progress_stages_loop(analysis_id: str) -> None:
    """W6-T4：后台任务，按 STAGE_PROGRESSION 时间表推进 DB 中的 stage / stage_progress。

    设计说明
    --------
    - 每个 stage 在其预算时长内把 `stage_progress` 从 0 平滑推到 99（完成那一刻 = 100，
      由下一个 stage 的开始覆盖；最后一个 stage 由 `_mark_completed` 覆盖到 100）
    - 推进步长 1 秒一次，给前端 3 秒轮询足够的"看见变化"机会
    - 主任务在 ai_engine 返回（成功 / 失败）后会 cancel 本 task；任何中间状态都
      可以接受（cancel 时 stage 停在哪儿就停在哪儿，主任务的 _mark_completed /
      _mark_failed 会覆写为终态）
    - 使用独立的 AsyncSession，每个写入事务都短小（避免长事务持有 session 锁）
    - 任何 DB 异常吞掉 + 继续推进；这层是装饰性 UI，不能因为一次写失败就崩
    """
    elapsed = 0  # 自该 stage 开始算起的秒数
    try:
        for stage_name, duration in STAGE_PROGRESSION:
            # 每秒更新一次 progress
            for sec in range(1, duration + 1):
                # progress 占据该 stage 的 0-99；最后由 _mark_completed 提升到 100
                progress = min(99, round(sec / duration * 99))
                try:
                    async with AsyncSessionLocal() as db:
                        analysis = await db.get(SwingAnalysis, analysis_id)
                        if analysis is None:
                            return
                        # 已 terminal 直接退出（_mark_completed/_mark_failed 已经写过）
                        if analysis.status in {"completed", "failed"}:
                            return
                        analysis.stage = stage_name
                        analysis.stage_progress = progress
                        await db.commit()
                except Exception as exc:  # pragma: no cover - 装饰性写入，吞掉
                    log.debug("stage_progress_write_failed", analysis_id=analysis_id, err=repr(exc))
                await asyncio.sleep(1)
                elapsed += 1
    except asyncio.CancelledError:
        # 被主任务 cancel：正常路径，不算错
        log.debug("stage_progress_cancelled", analysis_id=analysis_id, elapsed=elapsed)
        raise


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
        qw = engine_result.get("quality_warnings")
        if isinstance(qw, list):
            analysis.quality_warnings = [str(x) for x in qw if x is not None]
        else:
            analysis.quality_warnings = None
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

        # W7-T3：分析成功 → 同步生成/更新当周训练计划；任何异常都不能影响主流程落库
        try:
            await training_service.generate_or_update_weekly(
                db,
                user_id=analysis.user_id,
                analysis_id=analysis.id,
                issues=engine_result.get("issues") or [],
            )
        except Exception as exc:
            log.warning(
                "training_plan.generate_failed",
                analysis_id=analysis.id,
                user_id=analysis.user_id,
                error=str(exc),
            )

        # W7-T4：被邀请者首次分析完成 → 结算 invitation（状态 registered → valid；
        # inviter 累计 5 人发 7 天会员）。同样不能阻断分析主流程。
        try:
            await invitation_service.settle_on_first_analysis(
                db, user_id=analysis.user_id, analysis_id=analysis.id
            )
        except Exception as exc:
            log.warning(
                "invitation.settle_failed",
                analysis_id=analysis.id,
                user_id=analysis.user_id,
                error=str(exc),
            )

        # 一次性订阅消息：分析完成提醒（commit 后发送；不阻断主流程）
        mini_openid: str | None = None
        if not analysis.is_sample:
            user_row = await db.get(User, analysis.user_id)
            if user_row is not None:
                user_row.has_completed_real_analysis = True
                mini_openid = user_row.wechat_openid or None

        await db.commit()

        if mini_openid:
            try:
                await send_analysis_completed_notification(
                    openid=mini_openid,
                    analysis_id=analysis.id,
                    overall_score=analysis.overall_score,
                    analyzed_at=analysis.analyzed_at,
                )
            except Exception as exc:
                log.warning(
                    "subscribe_message.unexpected_error",
                    analysis_id=analysis.id,
                    error=str(exc),
                )


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
    "STAGE_PROGRESSION",
    "_progress_stages_loop",
    "_run_swing_analysis_async",
    "run_swing_analysis",
]
