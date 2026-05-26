"""AI Engine 服务入口."""

import logging
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app import __version__
from app.config import settings
from app.errors import PipelineError
from app.mock_pipeline import run_mock_analysis
from app.schemas import AnalyzeRequest, AnalyzeResult, PrecheckRequest, PrecheckResult
from app.version_router import (
    ENGINE_V1,
    ENGINE_V2,
    RolloutDowngradeRequiresForce,
    get_engine_version,
    get_rollout_pct,
    set_rollout_pct,
)


def _setup_logging() -> None:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


_setup_logging()
log = structlog.get_logger("ai_engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("ai_engine_starting", mock_mode=settings.AI_ENGINE_MOCK_MODE, version=__version__)
    yield
    log.info("ai_engine_stopping")


app = FastAPI(
    title="领翼golf · Engine",
    description="挥杆视频分析 AI 引擎",
    version=__version__,
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
)


@app.get("/health", summary="健康检查")
async def health():
    return {
        "status": "ok",
        "version": __version__,
        "mock_mode": settings.AI_ENGINE_MOCK_MODE,
        "rollout_pct": get_rollout_pct(),
    }


@app.post(
    "/analyze",
    summary="执行挥杆分析",
    response_model=AnalyzeResult,
)
async def analyze(req: AnalyzeRequest) -> AnalyzeResult:
    """分析单个视频。

    - **mock 模式**（`AI_ENGINE_MOCK_MODE=true`）：随机生成符合 schema 的报告
    - **真实模式**（默认）：`real_pipeline`（MediaPipe 姿态 → 阶段 → 评分 → 诊断 → 骨骼衍生视频）

    M7-14：每次请求按 ``user_id_hint`` 哈希分桶决定走 V1 / V2。
    """

    # 1) 路由判定（mock 模式优先；真实模式按灰度分桶）
    if settings.AI_ENGINE_MOCK_MODE:
        engine_version = ENGINE_V1  # mock 永远视为 v1
    elif req.force_engine_version:
        engine_version = req.force_engine_version
    else:
        engine_version = get_engine_version(req.user_id_hint)

    log.info(
        "analyze_start",
        analysis_id=req.analysis_id,
        video_url=req.video_url,
        engine_version=engine_version,
        rollout_pct=get_rollout_pct(),
    )

    if settings.AI_ENGINE_MOCK_MODE:
        result = await run_mock_analysis(req)
    else:
        try:
            # V2 管线尚未独立模块，暂时同走 real_pipeline（M7-07/M7-10 接力实现独立 V2 分支）
            # 一旦 V2 模块就位，这里改成：
            #   if engine_version == ENGINE_V2:
            #       from app.pipeline.real_pipeline_v2 import run_real_analysis_v2
            #       result = await run_real_analysis_v2(req)
            from app.pipeline.real_pipeline import run_real_analysis

            result = await run_real_analysis(req)
        except PipelineError as exc:
            log.warning(
                "pipeline_error",
                analysis_id=req.analysis_id,
                code=exc.code,
                error=str(exc),
                engine_version=engine_version,
            )
            result = AnalyzeResult(
                analysis_id=req.analysis_id,
                status="failed",
                engine_version=engine_version,
                error_code=exc.code,
                error_message=exc.user_message,
            )

    # 2) 强制把灰度判定写回 result，覆盖 pipeline 内部默认值
    result.engine_version = engine_version

    log.info(
        "analyze_done",
        analysis_id=req.analysis_id,
        status=result.status,
        overall_score=result.overall_score,
        engine_version=engine_version,
    )
    return result


@app.post(
    "/admin/engine-rollout",
    summary="M7-14 设置 V2 灰度比例",
)
async def admin_engine_rollout(payload: dict) -> dict:
    """设置 ``M7_V2_ROLLOUT_PCT``（FR-3 配置中心）.

    Body: ``{"pct": 25, "force": false}``；``new_pct < previous_pct`` 需 force=True。

    生产环境应在 nginx / API gateway 层加 admin token 拦截（本任务仅暴露
    ai_engine 内部端点，不直接接到公网）。
    """

    pct = int(payload.get("pct", 0))
    force = bool(payload.get("force", False))
    try:
        out = set_rollout_pct(pct, force=force)
    except RolloutDowngradeRequiresForce as exc:
        return {
            "code": 40010,
            "message": str(exc),
            "confirm_required": True,
        }
    return {"code": 0, "data": out}


@app.post(
    "/precheck",
    summary="上传后快速质量预检（O-08）",
    response_model=PrecheckResult,
)
async def precheck(req: PrecheckRequest) -> PrecheckResult:
    """5s 扫描预算内的画质/抖动硬门槛；不跑 pose / 评分。"""
    log.info("precheck_start", analysis_id=req.analysis_id, video_url=req.video_url)
    if settings.AI_ENGINE_MOCK_MODE:
        return PrecheckResult(
            analysis_id=req.analysis_id,
            status="passed",
            quality_warnings=[],
            elapsed_ms=0,
            scan_elapsed_ms=0,
        )
    from app.pipeline.precheck import run_precheck

    result = run_precheck(analysis_id=req.analysis_id, video_url=req.video_url)
    log.info(
        "precheck_done",
        analysis_id=req.analysis_id,
        status=result.status,
        elapsed_ms=result.elapsed_ms,
        scan_elapsed_ms=result.scan_elapsed_ms,
    )
    return PrecheckResult(
        analysis_id=result.analysis_id,
        status=result.status,
        quality_warnings=result.quality_warnings,
        error_code=result.error_code,
        error_message=result.error_message,
        elapsed_ms=result.elapsed_ms,
        scan_elapsed_ms=result.scan_elapsed_ms,
    )
