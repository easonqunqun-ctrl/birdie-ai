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
from app.schemas import AnalyzeRequest, AnalyzeResult


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
    """
    log.info("analyze_start", analysis_id=req.analysis_id, video_url=req.video_url)

    if settings.AI_ENGINE_MOCK_MODE:
        result = await run_mock_analysis(req)
    else:
        # 真实 pipeline：preprocess → pose → phases → features → scoring → diagnose → recommend
        # PipelineError 在这里统一捕获为 failed 结果（业务错误码 + 友好文案）；
        # 其它意外异常冒泡到 FastAPI 默认 500，由后端 Celery worker 重试/fallback 到 mock
        # （docs/14 T4 任务会在 backend 侧实现 fallback）。
        try:
            from app.pipeline.real_pipeline import run_real_analysis

            result = await run_real_analysis(req)
        except PipelineError as exc:
            log.warning(
                "pipeline_error",
                analysis_id=req.analysis_id,
                code=exc.code,
                error=str(exc),
            )
            result = AnalyzeResult(
                analysis_id=req.analysis_id,
                status="failed",
                error_code=exc.code,
                error_message=exc.user_message,
            )

    log.info(
        "analyze_done",
        analysis_id=req.analysis_id,
        status=result.status,
        overall_score=result.overall_score,
    )
    return result
