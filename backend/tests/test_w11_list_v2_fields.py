"""P2-W11 · 验证 ``GET /v1/analyses`` 列表 schema 返回 V2 ``engine_version`` 与
``analysis_confidence`` 字段，让客户端历史卡片可以贴可信度小标签 / V2 角标。

W10 已经把 V2 六字段落到了 ``swing_analyses`` 主表，但**列表 schema**
（``AnalysisListItem``）一直只有 6 个老字段；前端只能在点开报告详情时才看到
``analysis_confidence`` ——历史列表卡片看不到"这条是 V2 高/中/低可信"的信号，
也没法在 V2 真流量下做"低可信报告建议重拍"的二次入口。

W11 的承诺：
1. 列表 schema 加 ``engine_version`` (默认 ``v1`` 兜底) + ``analysis_confidence``
   (``float | None``)；老 V1 报告不会出 ValidationError。
2. service.list_analyses 把 ORM 列直接透传到 schema，老报告 ``engine_version``
   缺省回退到 ``"v1"``。
3. NaN / Inf / 越界 confidence → ``None``，前端不渲染小标签，不让 Pydantic 在
   边界 validation 抛 500。

设计选择：跟 W10 一样直接操作 DB，避开 mock_login + upload 全链路，让本测在 CVM
prod 环境也能跑。
"""

from __future__ import annotations

import math
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
            wechat_openid=f"o_w11_{new_id('mock')}",
            nickname="W11 list test user",
            invite_code=new_id("inv")[-6:].upper(),
        )
        db.add(user)
        await db.commit()
    return user_id


async def _insert_analysis(
    user_id: str,
    *,
    engine_version: str = "v1",
    analysis_confidence: Any = None,
    status: str = "completed",
    club_type: str = "iron_7",
) -> str:
    """插入一条 swing_analysis 行，可指定 engine_version / analysis_confidence."""
    from app.core.database import AsyncSessionLocal

    analysis_id = new_id("ana")
    async with AsyncSessionLocal() as db:
        analysis = SwingAnalysis(
            id=analysis_id,
            user_id=user_id,
            status=status,
            stage="completed",
            stage_progress=100,
            camera_angle="face_on",
            club_type=club_type,
            video_url="https://x/v.mp4",
            video_duration=8.0,
            engine_version=engine_version,  # type: ignore[arg-type]
            analysis_confidence=analysis_confidence,
            overall_score=72,
            created_at=datetime.now(UTC),
            analyzed_at=datetime.now(UTC),
        )
        db.add(analysis)
        await db.commit()
    return analysis_id


@pytest.mark.asyncio
async def test_list_analyses_returns_v2_engine_version_and_confidence():
    """V2 报告：list_analyses 透传 engine_version + analysis_confidence."""
    from app.core.database import AsyncSessionLocal
    from app.schemas.analysis import AnalysisListQuery
    from app.services.analysis_service import list_analyses

    user_id = await _insert_user()
    v2_id = await _insert_analysis(
        user_id, engine_version="v2", analysis_confidence=0.83
    )

    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        items, total, _capped = await list_analyses(
            user=user,
            query=AnalysisListQuery(page=1, page_size=20),
            db=db,
        )

    assert total == 1
    assert len(items) == 1
    assert items[0].id == v2_id
    assert items[0].engine_version == "v2"
    assert items[0].analysis_confidence == pytest.approx(0.83)


@pytest.mark.asyncio
async def test_list_analyses_v1_legacy_defaults_engine_version_and_null_confidence():
    """老 V1 报告：engine_version 兜底 'v1'，analysis_confidence None → 前端不渲染小标签."""
    from app.core.database import AsyncSessionLocal
    from app.schemas.analysis import AnalysisListQuery
    from app.services.analysis_service import list_analyses

    user_id = await _insert_user()
    await _insert_analysis(user_id, engine_version="v1", analysis_confidence=None)

    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        items, _total, _capped = await list_analyses(
            user=user,
            query=AnalysisListQuery(page=1, page_size=20),
            db=db,
        )

    assert len(items) == 1
    assert items[0].engine_version == "v1"
    assert items[0].analysis_confidence is None


@pytest.mark.asyncio
async def test_list_analyses_sanitizes_malformed_confidence():
    """NaN / Inf / 越界 confidence → None 或 clamp，不让 Pydantic 抛 500."""
    from app.core.database import AsyncSessionLocal
    from app.schemas.analysis import AnalysisListQuery
    from app.services.analysis_service import list_analyses

    user_id = await _insert_user()
    # 三条 V2 报告：NaN / Inf / 越界 1.5 / 越界 -0.2 / 合法 0.5
    # PostgreSQL Numeric 不让落 NaN/Inf，所以这里只能覆盖越界 + None
    # NaN/Inf 的兜底逻辑在 _coerce_list_confidence 内部用 math.isfinite 兜，单测无法
    # 直接构造 ORM 异常值——这里用越界值验证 clamp 行为已经足够。
    await _insert_analysis(
        user_id, engine_version="v2", analysis_confidence=1.5, club_type="driver"
    )
    await _insert_analysis(
        user_id, engine_version="v2", analysis_confidence=-0.2, club_type="iron_7"
    )
    await _insert_analysis(
        user_id, engine_version="v2", analysis_confidence=0.5, club_type="putter"
    )

    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        items, _total, _capped = await list_analyses(
            user=user,
            query=AnalysisListQuery(page=1, page_size=20),
            db=db,
        )

    confidences = {it.club_type: it.analysis_confidence for it in items}
    assert confidences["driver"] == pytest.approx(1.0)  # clamp 1.5 → 1.0
    assert confidences["iron_7"] == pytest.approx(0.0)  # clamp -0.2 → 0.0
    assert confidences["putter"] == pytest.approx(0.5)


def test_coerce_list_confidence_handles_nan_inf_and_garbage():
    """_coerce_list_confidence 兜底单测：NaN / Inf / 字符串 / None → None."""
    from app.services.analysis_service import _coerce_list_confidence

    assert _coerce_list_confidence(None) is None
    assert _coerce_list_confidence(math.nan) is None
    assert _coerce_list_confidence(math.inf) is None
    assert _coerce_list_confidence(-math.inf) is None
    assert _coerce_list_confidence("not_a_number") is None
    assert _coerce_list_confidence("0.7") == pytest.approx(0.7)
    assert _coerce_list_confidence(0.5) == pytest.approx(0.5)
    assert _coerce_list_confidence(1.5) == pytest.approx(1.0)
    assert _coerce_list_confidence(-0.2) == pytest.approx(0.0)
