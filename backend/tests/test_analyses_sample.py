"""M2-T6 示例分析报告接口（/v1/analyses/sample）的集成测试。

覆盖：
- 匿名调用（未带 Token）也能拿到完整示例报告
- 登录用户调用同一接口，结果完全一致
- 返回结构满足前端 `AnalysisReportResponse` 的所有必选字段
- 示例 id 固定为 "sample"；不生成任何数据库记录
- 不影响 /v1/analyses 列表（沙盒样本不入库）
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_sample_available_anonymously(client: AsyncClient) -> None:
    """未登录用户也能访问示例报告（MVP §3.6 的关键入口）。"""
    resp = await client.get("/v1/analyses/sample")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["id"] == "sample"
    assert data["status"] == "completed"
    # overall_score 必须在 good/great 档位（示例要"有瑕疵但不失败"）
    assert 70 <= data["overall_score"] <= 85
    assert data["score_level"] in {"good", "great"}


@pytest.mark.asyncio
async def test_sample_full_report_shape(client: AsyncClient) -> None:
    """返回结构必须覆盖前端 AnalysisReportResponse 的 6 大区域字段。"""
    resp = await client.get("/v1/analyses/sample")
    data = resp.json()["data"]

    # 视频回放
    assert data["video_url"].startswith("http")
    assert data["skeleton_video_url"]  # mock 期与原视频同源
    assert data["thumbnail_url"]

    # 综合评分
    assert isinstance(data["overall_score"], int)

    # 六维雷达
    assert set(data["phase_scores"].keys()) == {
        "setup", "backswing", "top", "downswing", "impact", "follow_through"
    }
    # 最弱项必须标记为 is_weakest（downswing）
    weakest = [k for k, v in data["phase_scores"].items() if v["is_weakest"]]
    assert weakest == ["downswing"]

    # 阶段时间戳
    assert set(data["phase_timestamps"].keys()) == set(data["phase_scores"].keys())

    # 问题诊断：至少 1 条 high + 1 条 medium
    severities = [i["severity"] for i in data["issues"]]
    assert "high" in severities
    assert "medium" in severities

    # 训练建议：和问题一一对应
    assert len(data["recommendations"]) >= 1
    drill_ids = {r["drill_id"] for r in data["recommendations"]}
    assert drill_ids.issubset(
        {"drill_towel_arm", "drill_hip_rotation", "drill_half_swing"}
    )


@pytest.mark.asyncio
async def test_sample_idempotent(client: AsyncClient) -> None:
    """示例数据必须稳定：连续两次请求完全一致（便于运营截图 / 自动化对比）。"""
    r1 = (await client.get("/v1/analyses/sample")).json()["data"]
    r2 = (await client.get("/v1/analyses/sample")).json()["data"]
    assert r1 == r2


@pytest.mark.asyncio
async def test_sample_with_auth_token_also_works(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """带 Token 访问也 OK；结果与匿名一致（示例报告与用户身份无关）。"""
    anonymous = (await client.get("/v1/analyses/sample")).json()["data"]
    logged_in = (
        await client.get("/v1/analyses/sample", headers=auth_headers)
    ).json()["data"]
    assert anonymous == logged_in


@pytest.mark.asyncio
async def test_sample_not_in_history_list(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """访问示例接口不应在用户的历史列表里留记录。"""
    # 先访问一次 sample
    await client.get("/v1/analyses/sample", headers=auth_headers)

    # 再查历史列表：对新用户应为空
    resp = await client.get("/v1/analyses", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 0
    assert data["items"] == []
