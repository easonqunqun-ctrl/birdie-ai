"""AI Engine HTTP 客户端封装（对齐 ai_engine/app/schemas.py）.

设计目标：
- 对 tasks 层暴露单一入口 `AIEngineClient.analyze(...)`。
- 返回 **dict**（而非 Pydantic 模型），因为后端侧 `app/schemas/analysis.py` 的
  `PhaseScore / PhaseTimestamps` 等与 ai_engine 侧结构**同名但不等价**（后端更严，
  例如后端 `PhaseWindow` 用 `start/end` float，ai_engine 返回 `dict[str, float]`）。
  task 侧直接按 dict 索引赋值给 ORM 的 JSONB 字段更直接、不易出错。
- 超时/连接错误**原样抛出**；重试交给 task 层决定（不耦合业务策略）。
"""

from __future__ import annotations

import httpx
import structlog

from app.config import settings

log = structlog.get_logger("integrations.ai_engine")


class AIEngineClient:
    def __init__(self, *, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.AI_ENGINE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else float(settings.AI_ENGINE_TIMEOUT)

    async def analyze(
        self,
        *,
        analysis_id: str,
        video_url: str,
        camera_angle: str,
        club_type: str,
        mode: str = "full_swing",
        user_id_hint: str | None = None,
        force_engine_version: str | None = None,
        selected_swing_index: int | None = None,
    ) -> dict:
        payload: dict = {
            "analysis_id": analysis_id,
            "video_url": video_url,
            "camera_angle": camera_angle,
            "club_type": club_type,
            "mode": mode,
        }
        # M7-14：传 user_id 让 ai_engine 做灰度分桶；老 ai_engine 容器忽略未知字段
        if user_id_hint:
            payload["user_id_hint"] = user_id_hint
        if force_engine_version:
            payload["force_engine_version"] = force_engine_version
        if selected_swing_index is not None:
            payload["selected_swing_index"] = selected_swing_index
        log.info("ai_engine_call_start", analysis_id=analysis_id, base_url=self.base_url)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/analyze", json=payload)
            # 非 2xx 视为引擎异常；上层按 timeout / 5xx 分别处理
            resp.raise_for_status()
            data = resp.json()
            log.info(
                "ai_engine_call_done",
                analysis_id=analysis_id,
                status=data.get("status"),
                overall_score=data.get("overall_score"),
                engine_version=data.get("engine_version"),
            )
            return data

    async def precheck(
        self,
        *,
        analysis_id: str,
        video_url: str,
    ) -> dict:
        """保留供运维/脚本抽检；生产 Celery 主路径已内联到 /analyze 早检，不再调用。"""
        payload = {
            "analysis_id": analysis_id,
            "video_url": video_url,
        }
        log.info("ai_engine_precheck_start", analysis_id=analysis_id, base_url=self.base_url)
        timeout = float(getattr(settings, "AI_ENGINE_PRECHECK_TIMEOUT", 20) or 20)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{self.base_url}/precheck", json=payload)
            resp.raise_for_status()
            data = resp.json()
            log.info(
                "ai_engine_precheck_done",
                analysis_id=analysis_id,
                status=data.get("status"),
                scan_elapsed_ms=data.get("scan_elapsed_ms"),
            )
            return data

    async def derive_skeleton(
        self,
        *,
        analysis_id: str,
        normalized_video_url: str | None = None,
        skeleton_data_url: str | None = None,
        video_url: str | None = None,
    ) -> dict:
        payload: dict = {"analysis_id": analysis_id}
        if normalized_video_url:
            payload["normalized_video_url"] = normalized_video_url
        if skeleton_data_url:
            payload["skeleton_data_url"] = skeleton_data_url
        if video_url:
            payload["video_url"] = video_url
        log.info(
            "ai_engine_derive_skeleton_start",
            analysis_id=analysis_id,
            base_url=self.base_url,
        )
        timeout = float(
            getattr(settings, "AI_ENGINE_DERIVE_SKELETON_TIMEOUT", 90) or 90
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{self.base_url}/derive-skeleton", json=payload)
            resp.raise_for_status()
            data = resp.json()
            log.info(
                "ai_engine_derive_skeleton_done",
                analysis_id=analysis_id,
                status=data.get("status"),
            )
            return data

    async def detect_swings(
        self,
        *,
        analysis_id: str,
        video_url: str,
    ) -> dict:
        payload = {
            "analysis_id": analysis_id,
            "video_url": video_url,
            "mode": "full_swing",
        }
        log.info(
            "ai_engine_detect_swings_start",
            analysis_id=analysis_id,
            base_url=self.base_url,
        )
        timeout = float(
            getattr(settings, "AI_ENGINE_DETECT_SWINGS_TIMEOUT", 120) or 120
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{self.base_url}/detect-swings", json=payload)
            resp.raise_for_status()
            data = resp.json()
            log.info(
                "ai_engine_detect_swings_done",
                analysis_id=analysis_id,
                status=data.get("status"),
                count=len(data.get("swing_candidates") or []),
            )
            return data


_default_client: AIEngineClient | None = None


def get_ai_engine() -> AIEngineClient:
    global _default_client
    if _default_client is None:
        _default_client = AIEngineClient()
    return _default_client


def reset_ai_engine() -> None:
    """仅测试/热重载用."""
    global _default_client
    _default_client = None
