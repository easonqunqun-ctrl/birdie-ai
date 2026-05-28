"""AI Engine 服务入口."""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from app import __version__
from app import metrics
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

    started_at = time.perf_counter()
    metrics.incr(f"{engine_version}_count")

    if settings.AI_ENGINE_MOCK_MODE:
        result = await run_mock_analysis(req)
    else:
        try:
            # P2-W4：V2 模块（real_pipeline_v2）就位；按灰度桶分流。
            # V1 路径保持原样；V2 路径目前仍复用 V1 pipeline（W34 PR 接 features
            # 外提后切到 diagnose_v2 重诊）。任何 V2 入口异常都不会影响 V1 桶用户。
            if engine_version == ENGINE_V2:
                from app.pipeline.real_pipeline_v2 import run_real_analysis_v2

                result = await run_real_analysis_v2(req)
            else:
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

    # 3) metrics：以 result.status 为准统一记账，避免 except 和外层重复 +1
    latency_ms = (time.perf_counter() - started_at) * 1000
    if result.status == "failed":
        metrics.incr(f"{engine_version}_errors")
    else:
        metrics.record_latency(engine_version, latency_ms)

    log.info(
        "analyze_done",
        analysis_id=req.analysis_id,
        status=result.status,
        overall_score=result.overall_score,
        engine_version=engine_version,
        latency_ms=round(latency_ms, 1),
    )
    return result


@app.get("/metrics", summary="W6 ENG-A1 · 进程级 V1/V2 计数器")
async def get_metrics() -> dict:
    """返回当前进程的 v1/v2 命中数、错误率、平均耗时、流量比。

    用法：``curl http://ai_engine:9000/metrics``；
    `v2_traffic_ratio` 与当前 `rollout_pct` 对齐说明灰度真的在按比例分流。
    """
    return {
        "rollout_pct": get_rollout_pct(),
        "mock_mode": settings.AI_ENGINE_MOCK_MODE,
        **metrics.snapshot(),
    }


class _RolloutPayload(BaseModel):
    """``/admin/engine-rollout`` 入参；只接受 0–100。"""

    pct: int = Field(..., ge=0, le=100, description="V2 灰度百分比")
    force: bool = Field(False, description="``new_pct < previous_pct`` 时需 True")


def _require_admin_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """W6 ENG-A2 · 可选 admin token 鉴权.

    - 环境变量 ``AI_ENGINE_ADMIN_TOKEN`` 未配 → 允许所有调用（与 W5 兼容，
      此时安全靠「容器只在 docker 内网 + 9100 端口未对公网」兜底）；
    - 配置后 → 必须带 ``X-Admin-Token`` header 且值匹配，否则 401。

    使用建议：CVM 上线后请在 ``.env.local`` 配 ``AI_ENGINE_ADMIN_TOKEN=<random>``，
    并让 backend 通过 ``httpx.headers`` 转发；这样即使将来不慎暴露 9100
    端口也能挡住盲扫。
    """
    expected = os.environ.get("AI_ENGINE_ADMIN_TOKEN")
    if not expected:
        return
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_admin_token",
        )


@app.post(
    "/admin/engine-rollout",
    summary="M7-14 设置 V2 灰度比例",
    dependencies=[Depends(_require_admin_token)],
)
async def admin_engine_rollout(payload: _RolloutPayload) -> dict:
    """设置 ``M7_V2_ROLLOUT_PCT``（FR-3 配置中心）.

    Body: ``{"pct": 25, "force": false}``；``new_pct < previous_pct`` 需 force=True。

    W6 ENG-A2：支持可选 ``X-Admin-Token`` header 鉴权（见 ``_require_admin_token``）；
    且依赖 ``redis`` 客户端（同 W6 加入 pyproject）真正把 pct 写进 Redis，
    多实例 60s TTL 内对齐。
    """
    try:
        out = set_rollout_pct(payload.pct, force=payload.force)
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
