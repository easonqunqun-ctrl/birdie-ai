"""W6-T4 测试：stage 推进 + 错误码透传/夹住的边界。

T4 在 backend 侧的两个新行为：
1. `_progress_stages_loop` 后台 task 按 STAGE_PROGRESSION 时间表写 DB stage / stage_progress
2. `_run_swing_analysis_async` 对 ai_engine 返回的 error_code 做范围校验：
   50100-50199 透传，否则按 50100 兜底（仍退配额）

不覆盖的（已有测试）：网络重试 / engine_failed 退配额 / completed 落库等。
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.models.analysis import SwingAnalysis
from app.tasks import analysis_tasks as tasks_mod
from app.tasks.analysis_tasks import (
    STAGE_PROGRESSION,
    _mark_processing,
    _progress_stages_loop,
    _run_swing_analysis_async,
)
from tests.fakes import FakeAIEngine, FakeMinioStorage


# ============================================================
# 工具：复制自 test_analyses_e2e._create_analysis
# ============================================================
async def _create_analysis(
    client: AsyncClient,
    headers: dict[str, str],
    fake_minio: FakeMinioStorage,
) -> str:
    t = await client.post(
        "/v1/analyses/upload-token",
        headers=headers,
        json={
            "file_name": "swing.mp4",
            "file_size": 2 * 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 8.0,
        },
    )
    data = t.json()["data"]
    fake_minio.mark_uploaded(data["key"], size=2 * 1024 * 1024)
    r = await client.post(
        "/v1/analyses",
        headers=headers,
        json={
            "upload_id": data["upload_id"],
            "camera_angle": "face_on",
            "club_type": "iron_7",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["analysis_id"]


# ============================================================
# stage 推进
# ============================================================


@pytest.mark.asyncio
async def test_progress_stages_loop_writes_progression(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    monkeypatch: pytest.MonkeyPatch,
):
    """跑两段 1s 的进度，看是否真的写到 DB（stage + progress）。"""
    monkeypatch.setattr(
        tasks_mod,
        "STAGE_PROGRESSION",
        [("preprocessing", 1), ("pose_estimating", 1)],
    )

    aid = await _create_analysis(client, auth_headers, fake_minio)
    await _mark_processing(aid)

    # 阻塞跑完整个推进序列（最多 ~2.2s）
    await asyncio.wait_for(_progress_stages_loop(aid), timeout=4.0)

    async with AsyncSessionLocal() as db:
        a = await db.get(SwingAnalysis, aid)
        assert a is not None
        # 最后一个 stage 的最后一秒：stage=pose_estimating, progress=99
        assert a.stage == "pose_estimating"
        assert a.stage_progress == 99


@pytest.mark.asyncio
async def test_progress_stages_loop_exits_when_status_terminal(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    monkeypatch: pytest.MonkeyPatch,
):
    """已 terminal 的 analysis：loop 一进 first iteration 就退出，不覆写。"""
    monkeypatch.setattr(
        tasks_mod,
        "STAGE_PROGRESSION",
        [("preprocessing", 5)],  # 长一点，确保不是因为时间到了才退出
    )

    aid = await _create_analysis(client, auth_headers, fake_minio)
    # 先把状态置为 terminal
    async with AsyncSessionLocal() as db:
        a = await db.get(SwingAnalysis, aid)
        a.status = "completed"
        a.stage = None
        a.stage_progress = 100
        await db.commit()

    # loop 应该在第一次 DB 读后立刻 return，不会写入
    await asyncio.wait_for(_progress_stages_loop(aid), timeout=2.0)

    async with AsyncSessionLocal() as db:
        a = await db.get(SwingAnalysis, aid)
        assert a.status == "completed"
        assert a.stage is None  # 没有被覆写
        assert a.stage_progress == 100


@pytest.mark.asyncio
async def test_progress_stages_loop_cancellation_is_clean(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    monkeypatch: pytest.MonkeyPatch,
):
    """create_task 后立刻 cancel：不应抛非 CancelledError，也不会写到任何"奇怪"状态。"""
    monkeypatch.setattr(
        tasks_mod,
        "STAGE_PROGRESSION",
        [("preprocessing", 100)],
    )

    aid = await _create_analysis(client, auth_headers, fake_minio)
    await _mark_processing(aid)

    task = asyncio.create_task(_progress_stages_loop(aid))
    await asyncio.sleep(1.2)  # 让它至少推进 1 秒
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    async with AsyncSessionLocal() as db:
        a = await db.get(SwingAnalysis, aid)
        # cancel 时停在 preprocessing 的 1/100 ≈ 1
        assert a.stage == "preprocessing"
        assert 1 <= a.stage_progress <= 5  # 给点余地：调度抖动


@pytest.mark.asyncio
async def test_run_swing_analysis_advances_stage_during_engine_call(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    use_fake_ai_engine: FakeAIEngine,
    monkeypatch: pytest.MonkeyPatch,
):
    """让 fake ai_engine sleep 1.5s 模拟真实推理，期间应能在 DB 看到 stage 变成 pose_estimating。

    这是对"主任务 + 后台 stage_task 协作"的最直接的端到端验证。
    """
    monkeypatch.setattr(
        tasks_mod,
        "STAGE_PROGRESSION",
        [("preprocessing", 1), ("pose_estimating", 5)],
    )

    use_fake_ai_engine.set_mode("ok")

    # 包一层 sleep 让 analyze 慢一点，模拟真实推理
    original_analyze = use_fake_ai_engine.analyze

    async def slow_analyze(**kwargs):
        await asyncio.sleep(1.6)  # 跨过 preprocessing 进 pose_estimating
        return await original_analyze(**kwargs)

    monkeypatch.setattr(use_fake_ai_engine, "analyze", slow_analyze)

    aid = await _create_analysis(client, auth_headers, fake_minio)

    # 启动主任务并发，1.3s 后偷看 stage（应该已经在 pose_estimating）
    main_task = asyncio.create_task(_run_swing_analysis_async(aid))
    await asyncio.sleep(1.3)

    async with AsyncSessionLocal() as db:
        a = await db.get(SwingAnalysis, aid)
        # 这时主任务还没结束，应该还在 processing + pose_estimating
        assert a.status == "processing"
        assert a.stage == "pose_estimating"

    # 等主任务跑完
    await main_task

    async with AsyncSessionLocal() as db:
        a = await db.get(SwingAnalysis, aid)
        assert a.status == "completed"
        assert a.stage is None
        assert a.stage_progress == 100


# ============================================================
# 错误码透传 / 夹住
# ============================================================


@pytest.mark.parametrize("err_code", [50101, 50102, 50103, 50104, 50105])
@pytest.mark.asyncio
async def test_engine_failed_known_codes_pass_through(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    use_fake_ai_engine: FakeAIEngine,
    err_code: int,
    monkeypatch: pytest.MonkeyPatch,
):
    """ai_engine 返回 50101-50105 的 5 个业务码 → 后端原样落库 + 退配额。"""
    monkeypatch.setattr(tasks_mod, "STAGE_PROGRESSION", [("preprocessing", 1)])
    use_fake_ai_engine.set_mode(
        "engine_failed",
        error_code=err_code,
        error_message=f"err {err_code}",
    )
    aid = await _create_analysis(client, auth_headers, fake_minio)
    await _run_swing_analysis_async(aid)

    s = (await client.get(f"/v1/analyses/{aid}/status", headers=auth_headers)).json()["data"]
    assert s["status"] == "failed"
    assert s["error"]["code"] == err_code
    assert s["error"]["quota_refunded"] is True


@pytest.mark.asyncio
async def test_engine_failed_unknown_code_clamps_to_50100(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    use_fake_ai_engine: FakeAIEngine,
    monkeypatch: pytest.MonkeyPatch,
):
    """ai_engine 返回非 50100-50199 段的码（异常路径）→ 后端兜底为 50100，仍退配额。"""
    monkeypatch.setattr(tasks_mod, "STAGE_PROGRESSION", [("preprocessing", 1)])
    use_fake_ai_engine.set_mode(
        "engine_failed",
        error_code=42,  # 越界
        error_message="bogus",
    )
    aid = await _create_analysis(client, auth_headers, fake_minio)
    await _run_swing_analysis_async(aid)

    s = (await client.get(f"/v1/analyses/{aid}/status", headers=auth_headers)).json()["data"]
    assert s["status"] == "failed"
    assert s["error"]["code"] == 50100
    assert s["error"]["quota_refunded"] is True


@pytest.mark.asyncio
async def test_engine_failed_missing_error_code_clamps_to_50100(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    monkeypatch: pytest.MonkeyPatch,
):
    """ai_engine 返回 status=failed 但忘了带 error_code → 后端兜底为 50100。"""
    monkeypatch.setattr(tasks_mod, "STAGE_PROGRESSION", [("preprocessing", 1)])

    class _NoCodeFakeEngine:
        async def analyze(self, **kwargs):
            return {
                "analysis_id": kwargs["analysis_id"],
                "status": "failed",
                # 没有 error_code 字段
                "error_message": "something broke",
            }

    monkeypatch.setattr(tasks_mod, "get_ai_engine", lambda: _NoCodeFakeEngine())
    aid = await _create_analysis(client, auth_headers, fake_minio)
    await _run_swing_analysis_async(aid)

    s = (await client.get(f"/v1/analyses/{aid}/status", headers=auth_headers)).json()["data"]
    assert s["error"]["code"] == 50100


# ============================================================
# STAGE_PROGRESSION 总时长 sanity check（防止以后改动累计超过 timeout）
# ============================================================


def test_stage_progression_total_under_timeout():
    """预算总和不应超过 AI_ENGINE_TIMEOUT（60s），否则 stage_task 会"超过引擎"挂死。"""
    from app.config import settings

    total = sum(d for _, d in STAGE_PROGRESSION)
    assert total <= settings.AI_ENGINE_TIMEOUT, (
        f"STAGE_PROGRESSION 总和 {total}s 超过 AI_ENGINE_TIMEOUT={settings.AI_ENGINE_TIMEOUT}s"
    )
