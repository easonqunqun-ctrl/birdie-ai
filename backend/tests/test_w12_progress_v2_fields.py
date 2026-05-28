"""P2-W12-1 · 验证 ``GET /v1/users/me/analysis-progress`` 进步曲线返回 V2
``engine_version`` 与 ``analysis_confidence`` 字段，让客户端 ProgressLineChart
能按 trust tier（高/中/低）给每个曲线点上不同颜色。

为什么必须做：W11 已经让历史**列表**支持 V2 trust 小标签，但「我的-成长曲线」
是用户**唯一**能横向看到"AI 这段时间到底拍得稳不稳"的入口；如果曲线只是单色，
低可信报告分数也会被画成跟高可信一样的点，相当于鼓励用户继续在低质量条件下
拍摄。本测把"列表 W11 透传"的同一套套路推到 progress API 上。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select

from app.core.security import new_id
from app.models import SwingAnalysis, User


async def _insert_user() -> str:
    """直接在 DB 建一个用户，返回 user_id."""
    from app.core.database import AsyncSessionLocal

    user_id = new_id("usr")
    async with AsyncSessionLocal() as db:
        user = User(
            id=user_id,
            wechat_openid=f"o_w12_{new_id('mock')}",
            nickname="W12 progress test user",
            invite_code=new_id("inv")[-6:].upper(),
        )
        db.add(user)
        await db.commit()
    return user_id


async def _insert_completed_analysis(
    user_id: str,
    *,
    engine_version: str = "v1",
    analysis_confidence: Any = None,
    overall_score: int = 70,
    analyzed_at: datetime | None = None,
) -> str:
    """插入一条 status=completed 的 swing_analysis 行，可指定 V2 字段."""
    from app.core.database import AsyncSessionLocal

    analysis_id = new_id("ana")
    async with AsyncSessionLocal() as db:
        analysis = SwingAnalysis(
            id=analysis_id,
            user_id=user_id,
            status="completed",
            stage="completed",
            stage_progress=100,
            camera_angle="face_on",
            club_type="iron_7",
            video_url="https://x/v.mp4",
            video_duration=8.0,
            engine_version=engine_version,  # type: ignore[arg-type]
            analysis_confidence=analysis_confidence,
            overall_score=overall_score,
            created_at=datetime.now(UTC),
            analyzed_at=analyzed_at or datetime.now(UTC),
        )
        db.add(analysis)
        await db.commit()
    return analysis_id


@pytest.mark.asyncio
async def test_progress_points_include_engine_version_and_confidence_for_v2():
    """V2 报告：progress points 透传 engine_version + analysis_confidence."""
    from app.core.database import AsyncSessionLocal
    from app.services.analysis_service import get_user_analysis_progress

    user_id = await _insert_user()
    v2_id = await _insert_completed_analysis(
        user_id,
        engine_version="v2",
        analysis_confidence=0.83,
        overall_score=78,
    )

    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        body = await get_user_analysis_progress(db, user)

    assert len(body.points) == 1
    assert body.points[0].analysis_id == v2_id
    assert body.points[0].engine_version == "v2"
    assert body.points[0].analysis_confidence == pytest.approx(0.83)
    assert body.points[0].overall_score == 78


@pytest.mark.asyncio
async def test_progress_points_v1_legacy_defaults_and_kept_db_default_confidence():
    """V1 老报告：engine_version 兜底 'v1'；DB server_default 让 confidence=1.0（无害，
    客户端按 engine_version=='v2' 路由）."""
    from app.core.database import AsyncSessionLocal
    from app.services.analysis_service import get_user_analysis_progress

    user_id = await _insert_user()
    await _insert_completed_analysis(
        user_id,
        engine_version="v1",
        analysis_confidence=None,
        overall_score=65,
    )

    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        body = await get_user_analysis_progress(db, user)

    assert len(body.points) == 1
    assert body.points[0].engine_version == "v1"
    # DB server_default 兜成 1.0；客户端 V1 报告永远不上 tier，所以无害
    assert body.points[0].analysis_confidence == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_progress_points_keep_time_ordering_with_mixed_engine_versions():
    """V1/V2 报告混排：仍按 analyzed_at 升序，且 engine_version/confidence 独立透传，
    客户端拿到的曲线能"按时间扫一眼看出最近 V2 trust tier 的趋势"。"""
    from app.core.database import AsyncSessionLocal
    from app.services.analysis_service import get_user_analysis_progress

    user_id = await _insert_user()
    t0 = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    t1 = datetime(2026, 5, 10, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 5, 20, 10, 0, tzinfo=UTC)
    await _insert_completed_analysis(
        user_id, engine_version="v1", overall_score=60, analyzed_at=t0
    )
    await _insert_completed_analysis(
        user_id,
        engine_version="v2",
        analysis_confidence=0.4,
        overall_score=70,
        analyzed_at=t1,
    )
    await _insert_completed_analysis(
        user_id,
        engine_version="v2",
        analysis_confidence=0.85,
        overall_score=82,
        analyzed_at=t2,
    )

    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        body = await get_user_analysis_progress(db, user)

    assert [p.overall_score for p in body.points] == [60, 70, 82]
    assert [p.engine_version for p in body.points] == ["v1", "v2", "v2"]
    # V1 fallback 1.0；V2 透传真实 confidence
    assert body.points[0].analysis_confidence == pytest.approx(1.0)
    assert body.points[1].analysis_confidence == pytest.approx(0.4)
    assert body.points[2].analysis_confidence == pytest.approx(0.85)
