"""M2-T2 端到端集成测试：Celery task 内核串联 ai_engine mock 后的完整链路。

覆盖：
1. 正常：创建任务 → 调 _run_swing_analysis_async → /status=completed → /report 返回完整字段
2. ai_engine 返回 status=failed → failed 落库 + 配额退回 + /status.error.quota_refunded=True
3. ai_engine 网络超时 → 重试 3 次耗尽后终态 failed + 退配额
4. ai_engine "flaky"：前 2 次超时第 3 次成功 → 最终 completed（验证重试机制）
5. 多任务独立：同一用户连跑 2 条都完整落库、互不干扰
6. 配额守恒：失败路径执行后，quota.analysis_remaining 恢复到调用前

通过 fixture `use_fake_ai_engine` monkeypatch `app.tasks.analysis_tasks.get_ai_engine`，
直接调 `_run_swing_analysis_async` 模拟 celery worker 消费（不经过 broker）。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.tasks.analysis_tasks import _run_swing_analysis_async
from tests.fakes import FakeAIEngine, FakeMinioStorage


async def _create_analysis(
    client: AsyncClient,
    headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    *,
    club_type: str = "iron_7",
    camera_angle: str = "face_on",
) -> str:
    """小工具：走 upload-token + MinIO mark_uploaded + POST /analyses，返回 analysis_id。"""
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
            "camera_angle": camera_angle,
            "club_type": club_type,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["analysis_id"]


@pytest.mark.asyncio
async def test_e2e_happy_path_writes_full_report(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    use_fake_ai_engine: FakeAIEngine,
):
    """正常链路：worker 跑完后 status=completed，/report 返回完整六维/issues/drills。"""
    use_fake_ai_engine.set_mode("ok")
    aid = await _create_analysis(client, auth_headers, fake_minio)

    # 模拟 worker 消费
    await _run_swing_analysis_async(aid)

    # status=completed
    s = (await client.get(f"/v1/analyses/{aid}/status", headers=auth_headers)).json()["data"]
    assert s["status"] == "completed"
    assert s["stage"] is None
    assert s["error"] is None

    # report
    rep = await client.get(f"/v1/analyses/{aid}", headers=auth_headers)
    assert rep.status_code == 200, rep.text
    body = rep.json()["data"]
    assert body["status"] == "completed"
    assert body["overall_score"] == 78
    assert body["score_level"] == "good"  # 78 ∈ [70, 79]
    assert body["phase_scores"]["downswing"]["is_weakest"] is True
    assert body["phase_timestamps"]["impact"]["start"] == 2.0
    assert body["skeleton_video_url"].endswith("_skeleton.mp4")
    assert len(body["issues"]) == 2
    assert body["issues"][0]["type"] == "casting"
    assert body["issues"][0]["key_frame_timestamp"] == 1.8
    assert len(body["recommendations"]) == 1
    assert body["recommendations"][0]["drill_id"] == "drill_towel_arm"
    assert body["analyzed_at"] is not None

    me = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me["has_completed_real_analysis"] is True


@pytest.mark.asyncio
async def test_e2e_engine_failed_refunds_quota(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    use_fake_ai_engine: FakeAIEngine,
):
    """ai_engine 返回 status=failed（画质差、未检测到人体等） → 落库 failed + 退配额。"""
    # 调用前 remaining
    me_before = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    before = me_before["quota"]["analysis_remaining"]

    use_fake_ai_engine.set_mode(
        "engine_failed", error_code=50102, error_message="视频中未检测到人体"
    )
    aid = await _create_analysis(client, auth_headers, fake_minio)

    # 创建后立刻 -1
    me_mid = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me_mid["quota"]["analysis_remaining"] == before - 1

    # worker 消费：落 failed + 退配额
    await _run_swing_analysis_async(aid)

    s = (await client.get(f"/v1/analyses/{aid}/status", headers=auth_headers)).json()["data"]
    assert s["status"] == "failed"
    assert s["error"]["code"] == 50102
    assert s["error"]["message"] == "视频中未检测到人体"
    assert s["error"]["quota_refunded"] is True

    # 配额回到调用前
    me_after = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me_after["quota"]["analysis_remaining"] == before

    # ai_engine analyze 只被调一次（failed 不走重试）
    assert use_fake_ai_engine.call_count == 1


@pytest.mark.asyncio
async def test_e2e_quality_failed_via_inline_precheck_in_analyze(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    use_fake_ai_engine: FakeAIEngine,
):
    """O-08：质量硬门槛失败已内联到 /analyze → failed + 退配额；不再单独 /precheck。"""
    me_before = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    before = me_before["quota"]["analysis_remaining"]

    use_fake_ai_engine.set_mode(
        "precheck_blocked",
        error_code=50102,
        error_message="画面抖动过大，请固定机位或使用三脚架后重拍",
    )
    aid = await _create_analysis(client, auth_headers, fake_minio)
    await _run_swing_analysis_async(aid)

    s = (await client.get(f"/v1/analyses/{aid}/status", headers=auth_headers)).json()["data"]
    assert s["status"] == "failed"
    assert s["error"]["code"] == 50102
    assert "抖动" in s["error"]["message"]
    assert s["error"]["quota_refunded"] is True

    me_after = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me_after["quota"]["analysis_remaining"] == before
    assert use_fake_ai_engine.call_count == 1
    assert not any(c.get("method") == "precheck" for c in use_fake_ai_engine.calls)
    assert any(c.get("method") == "analyze" for c in use_fake_ai_engine.calls)


@pytest.mark.asyncio
async def test_e2e_timeout_exhausts_retries_and_refunds(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    use_fake_ai_engine: FakeAIEngine,
    monkeypatch: pytest.MonkeyPatch,
):
    """ai_engine 持续超时 → 重试 3 次（1 + 2 = 2 次额外）耗尽 → 终态 failed + 退配额。"""
    # 去掉指数退避的等待，免得测试跑 3 秒
    monkeypatch.setattr("app.tasks.analysis_tasks.RETRY_BACKOFF_BASE_SECONDS", 0)

    use_fake_ai_engine.set_mode("timeout")
    me_before = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    before = me_before["quota"]["analysis_remaining"]

    aid = await _create_analysis(client, auth_headers, fake_minio)
    await _run_swing_analysis_async(aid)

    # 状态 failed，错误码 50100 （AI 引擎不可达 transport 级 — W6-T6 拆出）
    s = (await client.get(f"/v1/analyses/{aid}/status", headers=auth_headers)).json()["data"]
    assert s["status"] == "failed"
    assert s["error"]["code"] == 50100
    assert "AI 引擎不可达" in s["error"]["message"]
    assert s["error"]["quota_refunded"] is True

    # 实际调用次数 = 3（1 次主调 + 2 次重试）
    assert use_fake_ai_engine.call_count == 3

    # 配额恢复
    me_after = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me_after["quota"]["analysis_remaining"] == before


@pytest.mark.asyncio
async def test_e2e_flaky_succeeds_after_retry(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    use_fake_ai_engine: FakeAIEngine,
    monkeypatch: pytest.MonkeyPatch,
):
    """前 2 次超时、第 3 次成功 → 最终 status=completed（验证重试机制真生效）。"""
    monkeypatch.setattr("app.tasks.analysis_tasks.RETRY_BACKOFF_BASE_SECONDS", 0)
    use_fake_ai_engine.set_mode("flaky", succeed_on_attempt=3)

    aid = await _create_analysis(client, auth_headers, fake_minio)
    await _run_swing_analysis_async(aid)

    s = (await client.get(f"/v1/analyses/{aid}/status", headers=auth_headers)).json()["data"]
    assert s["status"] == "completed"
    assert use_fake_ai_engine.call_count == 3

    # 配额 **不** 退回（成功了）
    me = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me["quota"]["analysis_remaining"] == 3 - 1


@pytest.mark.asyncio
async def test_e2e_multiple_analyses_independent(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    use_fake_ai_engine: FakeAIEngine,
):
    """同一用户连创 2 条任务，分别消费都能完整落库、互不干扰。"""
    use_fake_ai_engine.set_mode("ok")

    aid1 = await _create_analysis(client, auth_headers, fake_minio, club_type="driver")
    aid2 = await _create_analysis(client, auth_headers, fake_minio, club_type="wedge")
    assert aid1 != aid2

    await _run_swing_analysis_async(aid1)
    await _run_swing_analysis_async(aid2)

    rep1 = (await client.get(f"/v1/analyses/{aid1}", headers=auth_headers)).json()["data"]
    rep2 = (await client.get(f"/v1/analyses/{aid2}", headers=auth_headers)).json()["data"]
    assert rep1["status"] == "completed"
    assert rep2["status"] == "completed"
    assert rep1["club_type"] == "driver"
    assert rep2["club_type"] == "wedge"
    # 两条记录的 issues 数量相同（来自同一 fake 模板），但 id 不同
    assert rep1["id"] != rep2["id"]
    assert len(rep1["issues"]) == len(rep2["issues"]) == 2


@pytest.mark.asyncio
async def test_e2e_worker_idempotent_on_terminal_analysis(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
    use_fake_ai_engine: FakeAIEngine,
):
    """一条已经 completed 的 analysis 被误消费第二次 → 不应重复写 issues/扣配额。"""
    use_fake_ai_engine.set_mode("ok")
    aid = await _create_analysis(client, auth_headers, fake_minio)
    await _run_swing_analysis_async(aid)

    rep_before = (await client.get(f"/v1/analyses/{aid}", headers=auth_headers)).json()["data"]
    issues_before = len(rep_before["issues"])

    # 再跑一次
    await _run_swing_analysis_async(aid)
    rep_after = (await client.get(f"/v1/analyses/{aid}", headers=auth_headers)).json()["data"]
    assert rep_after["status"] == "completed"
    assert len(rep_after["issues"]) == issues_before  # 没有加倍
    assert rep_after["analyzed_at"] == rep_before["analyzed_at"]  # 也没被覆盖
