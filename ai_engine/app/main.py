"""AI Engine 服务入口."""

import logging
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app import __version__
from app.config import settings
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
    title="小鸟 AI · Engine",
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

    - **mock 模式**：随机生成符合 schema 的报告（2-5 秒）
    - **真实模式**：W6 接入 MediaPipe + 评分模型（待实现）
    """
    log.info("analyze_start", analysis_id=req.analysis_id, video_url=req.video_url)

    if settings.AI_ENGINE_MOCK_MODE:
        result = await run_mock_analysis(req)
    else:
        # TODO W6：接入 real_pipeline
        from app.schemas import AnalyzeResult as AR
        result = AR(
            analysis_id=req.analysis_id,
            status="failed",
            error_code=50101,
            error_message="real pipeline not implemented yet, set AI_ENGINE_MOCK_MODE=true",
        )

    log.info(
        "analyze_done",
        analysis_id=req.analysis_id,
        status=result.status,
        overall_score=result.overall_score,
    )
    return result
