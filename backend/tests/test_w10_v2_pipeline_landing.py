"""P2-W10 · 验证 ai_engine V2 引擎产物（W7+W8+W9）真正落库到 swing_analyses + 子表，
并通过 GET /v1/analyses/{id} 端到端透传到客户端。

为什么单独建一个测试文件
------------------------
W10 之前 backend `_mark_completed` 完全丢弃 ai_engine 返回的：
- ``analysis_confidence`` / ``feature_confidences`` / ``engine_warnings`` （主报告）
- ``issues[].confidence`` / ``issues[].confidence_tier`` （子记录）

导致客户端不管 V2 多牛逼都只能看到 schema 默认值（1.0 / {} / null）。本测验证：
1. _mark_completed 把这些字段全部落到对应列；
2. GET /v1/analyses/{id} 返回里包含相同值；
3. 字段缺失 / NaN / 类型异常时不破坏主写入路径（防御性容错）。

W10 这套实现的核心承诺就是这条管道——若回归，客户端 V2 兑现立刻退化为纯文本报告。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from sqlalchemy import select

from app.models import SwingAnalysis
from app.models.analysis import AnalysisIssue


def _v2_engine_result(analysis_id: str) -> dict[str, Any]:
    """合成"长得像 V2 引擎完整返回"的 dict，覆盖 W7+W8+W9 全部字段."""
    return {
        "analysis_id": analysis_id,
        "status": "completed",
        "engine_version": "v2",
        "overall_score": 72,
        "phase_scores": {
            "setup": {"score": 80, "label": "站位准备", "is_weakest": False},
        },
        "phase_timestamps": {"setup": {"start": 0.0, "end": 0.8}},
        "issues": [
            {
                "type": "casting",
                "name": "抛杆（Casting）",
                "severity": "high",
                "description": "下杆初期手腕过早释放。",
                "key_frame_timestamp": 1.8,
                "confidence": 0.91,
                "confidence_tier": "confirmed",
            },
            {
                "type": "early_extension",
                "name": "提前伸展",
                "severity": "medium",
                "description": "髋部过早向球方向移动。",
                "key_frame_timestamp": 1.9,
                "confidence": 0.55,
                "confidence_tier": "hidden",
            },
        ],
        "recommendations": [
            {"drill_id": "drill_towel_arm", "target_issue": "casting"}
        ],
        "quality_warnings": [],
        "analysis_confidence": 0.83,
        "feature_confidences": {
            "x_factor": 0.92,
            "tempo_ratio": 0.78,
            "spine_angle_setup": 0.85,
        },
        "engine_warnings": [
            {"code": "decoded_hevc", "level": "info", "detail": "codec=hevc", "ts": 1.2},
            {"code": "fps_downsampled", "level": "info", "detail": "raw 60fps vs V2 target 30fps", "ts": 1.3},
        ],
        "skeleton_video_url": "https://x/skeleton.mp4",
        "thumbnail_url": "https://x/thumb.jpg",
    }


async def _create_analysis_and_get_id(client, auth_headers, fake_minio) -> str:
    """快速建一个 completed 之前的 analysis，返回 analysis_id."""
    blob = b"fake-mp4-bytes-" + b"x" * 2048
    token = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "swing.mp4",
            "file_size": len(blob),
            "file_type": "video/mp4",
            "duration": 8.0,
        },
    )
    assert token.status_code == 200, token.text
    upload_id = token.json()["data"]["upload_id"]
    await client.post(
        f"/v1/analyses/uploads/{upload_id}/video",
        headers=auth_headers,
        files={"file": ("swing.mp4", blob, "video/mp4")},
    )
    create = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={"upload_id": upload_id, "camera_angle": "face_on", "club_type": "iron_7"},
    )
    assert create.status_code == 200, create.text
    return create.json()["data"]["analysis_id"]


@pytest.mark.asyncio
async def test_mark_completed_lands_v2_confidence_and_engine_warnings(
    client, auth_headers, fake_minio
):
    """_mark_completed 真把 V2 引擎 6 字段落到 DB."""
    from app.db.session import AsyncSessionLocal
    from app.tasks.analysis_tasks import _mark_completed

    analysis_id = await _create_analysis_and_get_id(client, auth_headers, fake_minio)
    await _mark_completed(analysis_id, _v2_engine_result(analysis_id))

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(SwingAnalysis).where(SwingAnalysis.id == analysis_id))
        ).scalar_one()
        assert row.engine_version == "v2"
        assert row.analysis_confidence == pytest.approx(0.83)
        assert row.feature_confidences == {
            "x_factor": 0.92, "tempo_ratio": 0.78, "spine_angle_setup": 0.85,
        }
        assert isinstance(row.engine_warnings, list)
        codes = {w["code"] for w in row.engine_warnings}
        assert "decoded_hevc" in codes
        assert "fps_downsampled" in codes

        issues = (
            await db.execute(
                select(AnalysisIssue)
                .where(AnalysisIssue.analysis_id == analysis_id)
                .order_by(AnalysisIssue.sort_order)
            )
        ).scalars().all()
        assert len(issues) == 2
        assert issues[0].confidence == pytest.approx(0.91)
        assert issues[0].confidence_tier == "confirmed"
        assert issues[1].confidence == pytest.approx(0.55)
        assert issues[1].confidence_tier == "hidden"


@pytest.mark.asyncio
async def test_get_report_returns_v2_confidence_and_engine_warnings(
    client, auth_headers, fake_minio
):
    """GET /v1/analyses/{id} 真把 V2 字段透传到客户端响应."""
    from app.tasks.analysis_tasks import _mark_completed

    analysis_id = await _create_analysis_and_get_id(client, auth_headers, fake_minio)
    await _mark_completed(analysis_id, _v2_engine_result(analysis_id))

    resp = await client.get(f"/v1/analyses/{analysis_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["engine_version"] == "v2"
    assert body["analysis_confidence"] == pytest.approx(0.83)
    assert body["feature_confidences"]["x_factor"] == pytest.approx(0.92)

    warnings = body["engine_warnings"]
    assert isinstance(warnings, list) and len(warnings) == 2
    assert {w["code"] for w in warnings} == {"decoded_hevc", "fps_downsampled"}
    assert all(w["level"] == "info" for w in warnings)

    issues = body["issues"]
    assert len(issues) == 2
    assert issues[0]["confidence"] == pytest.approx(0.91)
    assert issues[0]["confidence_tier"] == "confirmed"
    assert issues[1]["confidence_tier"] == "hidden"


@pytest.mark.asyncio
async def test_mark_completed_handles_missing_v2_fields_gracefully(
    client, auth_headers, fake_minio
):
    """V1 引擎或老 ai_engine 返回不含新字段时 → 用 model 默认值不崩."""
    from app.db.session import AsyncSessionLocal
    from app.tasks.analysis_tasks import _mark_completed

    analysis_id = await _create_analysis_and_get_id(client, auth_headers, fake_minio)
    v1_like = _v2_engine_result(analysis_id)
    v1_like["engine_version"] = "v1"
    v1_like.pop("analysis_confidence", None)
    v1_like.pop("feature_confidences", None)
    v1_like.pop("engine_warnings", None)
    for it in v1_like["issues"]:
        it.pop("confidence", None)
        it.pop("confidence_tier", None)

    await _mark_completed(analysis_id, v1_like)

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(SwingAnalysis).where(SwingAnalysis.id == analysis_id))
        ).scalar_one()
        assert row.engine_version == "v1"
        # model 列 NOT NULL DEFAULT 1.0
        assert row.analysis_confidence == pytest.approx(1.0)
        assert row.feature_confidences is None
        assert row.engine_warnings is None

        issues = (
            await db.execute(
                select(AnalysisIssue).where(AnalysisIssue.analysis_id == analysis_id)
            )
        ).scalars().all()
        for it in issues:
            assert it.confidence is None
            assert it.confidence_tier is None


@pytest.mark.asyncio
async def test_mark_completed_rejects_malformed_v2_values(
    client, auth_headers, fake_minio
):
    """V2 字段类型异常 / NaN / 未知 tier → 容错丢弃，不破坏主写入路径."""
    import math

    from app.db.session import AsyncSessionLocal
    from app.tasks.analysis_tasks import _mark_completed

    analysis_id = await _create_analysis_and_get_id(client, auth_headers, fake_minio)
    bad = _v2_engine_result(analysis_id)
    bad["analysis_confidence"] = math.nan  # NaN
    bad["feature_confidences"] = {"x_factor": "not_a_number", "tempo_ratio": 0.7}
    bad["engine_warnings"] = [
        {"code": "decoded_hevc", "level": "info"},  # 合法
        {"level": "warn"},  # 缺 code → 丢弃
        "not-a-dict",  # 类型错误 → 丢弃
    ]
    bad["issues"][0]["confidence"] = math.inf
    bad["issues"][1]["confidence_tier"] = "unknown_tier_value"

    await _mark_completed(analysis_id, bad)

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(SwingAnalysis).where(SwingAnalysis.id == analysis_id))
        ).scalar_one()
        # NaN 被拒，保留 model 默认 1.0
        assert row.analysis_confidence == pytest.approx(1.0)
        # 字符串 value 被过滤，只有 tempo_ratio 留下
        assert row.feature_confidences == {"tempo_ratio": 0.7}
        # 仅合法条目落库
        assert len(row.engine_warnings) == 1
        assert row.engine_warnings[0]["code"] == "decoded_hevc"

        issues = (
            await db.execute(
                select(AnalysisIssue)
                .where(AnalysisIssue.analysis_id == analysis_id)
                .order_by(AnalysisIssue.sort_order)
            )
        ).scalars().all()
        # Inf 被拒
        assert issues[0].confidence is None
        # 未知 tier 被拒
        assert issues[1].confidence_tier is None
