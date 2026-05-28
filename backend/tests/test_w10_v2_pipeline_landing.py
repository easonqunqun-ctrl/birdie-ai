"""P2-W10 · 验证 ai_engine V2 引擎产物（W7+W8+W9）真正落库到 swing_analyses + 子表，
并通过 service 层 get_report 透传到客户端响应。

为什么单独建一个测试文件
------------------------
W10 之前 backend `_mark_completed` 完全丢弃 ai_engine 返回的：
- ``analysis_confidence`` / ``feature_confidences`` / ``engine_warnings`` （主报告）
- ``issues[].confidence`` / ``issues[].confidence_tier`` （子记录）

导致客户端不管 V2 多牛逼都只能看到 schema 默认值（1.0 / {} / null）。本测验证：
1. _mark_completed 把这些字段全部落到对应列；
2. service.get_report 返回的 AnalysisReportResponse 包含相同值；
3. 字段缺失 / NaN / 类型异常时不破坏主写入路径（防御性容错）。

W10 这套实现的核心承诺就是这条管道——若回归，客户端 V2 兑现立刻退化为纯文本报告。

设计选择：直接操作 DB
----------------------
本测不走 HTTP login → upload-token → upload → create → process 全链路（那需要
``WECHAT_MOCK_LOGIN=true`` + minio 替身），改用 ``insert_seed`` 直接在 DB 写
SwingAnalysis 行模拟「analyze 任务即将完成」的状态。这样：
- 在 CVM 生产环境（mock_login=false）也能跑；
- 测试聚焦"落库 + 序列化"逻辑，不被上游 HTTP 链路噪声干扰；
- 跑得更快。
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select

from app.core.security import new_id
from app.models import SwingAnalysis, User
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
            {"code": "fps_downsampled", "level": "info", "detail": "raw 60fps", "ts": 1.3},
        ],
        "skeleton_video_url": "https://x/skeleton.mp4",
        "thumbnail_url": "https://x/thumb.jpg",
    }


async def _insert_user_and_analysis() -> tuple[str, str]:
    """直接在 DB 建一个 user + 一个 status=processing 的 analysis，返回 (user_id, analysis_id)."""
    from app.db.session import AsyncSessionLocal

    user_id = new_id("usr")
    analysis_id = new_id("ana")
    async with AsyncSessionLocal() as db:
        user = User(
            id=user_id,
            wechat_openid=f"o_w10_{new_id('mock')}",
            nickname="W10 test user",
            invite_code=new_id("inv")[-6:].upper(),
        )
        db.add(user)
        analysis = SwingAnalysis(
            id=analysis_id,
            user_id=user_id,
            status="processing",
            stage="diagnosing",
            stage_progress=80,
            camera_angle="face_on",
            club_type="iron_7",
            video_url="https://x/v.mp4",
            video_duration=8.0,
            engine_version="v1",  # 初始；_mark_completed 会改写为 v2
            created_at=datetime.now(UTC),
        )
        db.add(analysis)
        await db.commit()
    return user_id, analysis_id


@pytest.mark.asyncio
async def test_mark_completed_lands_v2_confidence_and_engine_warnings():
    """_mark_completed 真把 V2 引擎 6 字段落到 DB."""
    from app.db.session import AsyncSessionLocal
    from app.tasks.analysis_tasks import _mark_completed

    _, analysis_id = await _insert_user_and_analysis()
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
async def test_get_report_returns_v2_confidence_and_engine_warnings():
    """service.get_report 真把 V2 字段透传到 AnalysisReportResponse."""
    from app.db.session import AsyncSessionLocal
    from app.services.analysis_service import get_report
    from app.tasks.analysis_tasks import _mark_completed

    user_id, analysis_id = await _insert_user_and_analysis()
    await _mark_completed(analysis_id, _v2_engine_result(analysis_id))

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        body = await get_report(analysis_id=analysis_id, user=user, db=db)

    assert body.engine_version == "v2"
    assert body.analysis_confidence == pytest.approx(0.83)
    assert body.feature_confidences["x_factor"] == pytest.approx(0.92)

    assert isinstance(body.engine_warnings, list) and len(body.engine_warnings) == 2
    assert {w.code for w in body.engine_warnings} == {"decoded_hevc", "fps_downsampled"}
    assert all(w.level == "info" for w in body.engine_warnings)

    assert len(body.issues) == 2
    assert body.issues[0].confidence == pytest.approx(0.91)
    assert body.issues[0].confidence_tier == "confirmed"
    assert body.issues[1].confidence_tier == "hidden"


@pytest.mark.asyncio
async def test_mark_completed_handles_missing_v2_fields_gracefully():
    """V1 引擎或老 ai_engine 返回不含新字段时 → 用 model 默认值不崩."""
    from app.db.session import AsyncSessionLocal
    from app.tasks.analysis_tasks import _mark_completed

    _, analysis_id = await _insert_user_and_analysis()
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
async def test_mark_completed_rejects_malformed_v2_values():
    """V2 字段类型异常 / NaN / 未知 tier → 容错丢弃，不破坏主写入路径."""
    from app.db.session import AsyncSessionLocal
    from app.tasks.analysis_tasks import _mark_completed

    _, analysis_id = await _insert_user_and_analysis()
    bad = _v2_engine_result(analysis_id)
    bad["analysis_confidence"] = math.nan
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
