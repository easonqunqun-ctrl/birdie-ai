"""P2-W16-A · ENG-05 · 同水平+同器材的得分分位（GET /v1/users/me/score-percentile）.

测试覆盖
========

A. **基础公式**（不打 DB · 纯函数）
   1. _calc_percentile(85, [70,75,80,82,84])  → 100
   2. _calc_percentile(75, [60,80,90,95,100]) → 20
   3. _calc_percentile(80, [80,80,80,80,80])  → 0  （平局不算击败）
   4. _calc_percentile(80, [10,20,30])        → None（样本量 < 5）
   5. _calc_median([])                          → None
   6. _calc_median([60,70,80])                  → 70
   7. _calc_median([60,70,80,90])               → 80（偶数取下中位数）

B. **service · 端到端**（落 DB · 与 W11 同款 fixture pattern）
   8. cohort_size < 5 → percentile/median = null（防止 1-2 人对比误导）
   9. cohort_size ≥ 5 + 用户分高 → percentile = 100
  10. cohort_size ≥ 5 + 用户分低 → percentile = 0
  11. cohort 不命中 user 自己（self-exclusion）
  12. cohort 严格按 club_type 过滤（不同 club_type 不混算）
  13. cohort 严格按 golf_level 过滤（user 有 level 时）
  14. 用户没填 golf_level → cohort 不限定 level（"全部水平"）
  15. 当前用户没有任何同 club_type 完成态分析 → user_score=null

C. **schema 兜底**
  16. cohort_label 包含中文（"中级 / 七号铁"）
  17. computed_at 是 timezone-aware UTC

设计选择：跟 W11 一样直接操作 DB，避开 mock_login + upload 全链路，让本测在 CVM
prod 环境也能跑。

CVM 隔离：每个 test 用 ``_uniq_level()`` 生成独特的 golf_level（绝不与现网数据撞）+
独特的 club_type（``iron_7`` 之外的非典型值），让测试既不污染真数据，也不被真
数据污染。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.security import new_id
from app.models import SwingAnalysis, User
from app.services.analysis_service import (
    _calc_median,
    _calc_percentile,
    _format_percentile_cohort_label,
    get_user_score_percentile,
)


def _uniq_level() -> str:
    """W16-A 测试隔离 · 选用合法的 golf_level 枚举值之一.

    DB 约束 ``chk_golf_level`` 限制取值 ∈ {beginner, elementary, intermediate, advanced}，
    所以测试不能用 random 字符串。改用 ``intermediate``——和 prod 真实数据同 level，
    但**靠 unique club_type 把 cohort 完全隔离**：service 查询条件是
    ``WHERE level=? AND club_type=?``，level 撞了无所谓，club_type 撞不上就行。
    """
    return "intermediate"


def _uniq_club() -> str:
    """每个测试独立的 club_type；用 ``test_<6char>``（13 char）.

    虽然 prod 里 club_type 一般是 ``iron_7`` / ``driver`` 等枚举值，但 DB 字段是
    String(20) 不约束，测试用合成值就完全不与真数据冲突。前端 W16-B 仍按 ``iron_7``
    等枚举调用，本测的 unique club_type 仅供后端 service 路径覆盖。
    """
    return f"test_{uuid.uuid4().hex[:6]}"


# ============================================================
# A. 纯函数 · _calc_percentile / _calc_median / _format_percentile_cohort_label
# ============================================================


def test_calc_percentile_user_beats_all() -> None:
    """W16-A · cohort 全员 < user → 100%."""
    assert _calc_percentile(85, [70, 75, 80, 82, 84]) == 100


def test_calc_percentile_user_low() -> None:
    """W16-A · 5 人 cohort, user_score 高于 1/5 → 20%."""
    assert _calc_percentile(75, [60, 80, 90, 95, 100]) == 20


def test_calc_percentile_all_tied() -> None:
    """W16-A · 平局不算击败，向下取整 → 0%."""
    assert _calc_percentile(80, [80, 80, 80, 80, 80]) == 0


def test_calc_percentile_below_min_cohort_returns_none() -> None:
    """W16-A · cohort_size < 5 → None（避免 1-2 人对比就出"击败 50%"）."""
    assert _calc_percentile(80, [10, 20, 30]) is None
    assert _calc_percentile(80, [10, 20, 30, 40]) is None
    assert _calc_percentile(80, []) is None


def test_calc_percentile_min_cohort_exact_5_works() -> None:
    """W16-A · cohort_size 刚好 5 → 出 percentile."""
    assert _calc_percentile(80, [70, 70, 70, 70, 70]) == 100


def test_calc_median_empty_returns_none() -> None:
    assert _calc_median([]) is None


def test_calc_median_odd() -> None:
    assert _calc_median([60, 70, 80]) == 70


def test_calc_median_even_uses_lower() -> None:
    """W16-A · 偶数长度取下中位数（保 int 不引浮点）."""
    assert _calc_median([60, 70, 80, 90]) == 80


def test_format_percentile_cohort_label_zh() -> None:
    """W16-A · 标签中文化：「中级 / 七号铁」."""
    assert _format_percentile_cohort_label("intermediate", "iron_7") == "中级 / 七号铁"


def test_format_percentile_cohort_label_unknown_level() -> None:
    """W16-A · golf_level=None → "全部水平 / xxx"."""
    assert _format_percentile_cohort_label(None, "driver") == "全部水平 / 一号木"


def test_format_percentile_cohort_label_unknown_club() -> None:
    """W16-A · 未知 club_type → 原样回显."""
    assert _format_percentile_cohort_label("intermediate", "exotic_club") == "中级 / exotic_club"


# ============================================================
# B. service 端到端 · 落 DB
# ============================================================


async def _insert_user(*, golf_level: str | None = None) -> str:
    """W11 同款 fixture：直接 DB 建用户，返回 user_id."""
    from app.core.database import AsyncSessionLocal

    user_id = new_id("usr")
    async with AsyncSessionLocal() as db:
        user = User(
            id=user_id,
            wechat_openid=f"o_w16a_{new_id('mock')}",
            nickname=f"W16-A test user {user_id[-6:]}",
            invite_code=new_id("inv")[-6:].upper(),
            golf_level=golf_level,
        )
        db.add(user)
        await db.commit()
    return user_id


async def _insert_analysis(
    user_id: str,
    *,
    overall_score: int,
    club_type: str = "iron_7",
    status: str = "completed",
    is_sample: bool = False,
) -> str:
    """W11 同款 fixture：插入一条 swing_analysis 行."""
    from app.core.database import AsyncSessionLocal

    analysis_id = new_id("ana")
    async with AsyncSessionLocal() as db:
        analysis = SwingAnalysis(
            id=analysis_id,
            user_id=user_id,
            status=status,
            stage="completed" if status == "completed" else "pending",
            stage_progress=100 if status == "completed" else 0,
            camera_angle="face_on",
            club_type=club_type,
            video_url="https://x/v.mp4",
            video_duration=8.0,
            engine_version="v1",
            overall_score=overall_score,
            is_sample=is_sample,
            created_at=datetime.now(UTC),
            analyzed_at=datetime.now(UTC),
        )
        db.add(analysis)
        await db.commit()
    return analysis_id


async def _build_cohort(
    *, golf_level: str, club_type: str, scores: list[int]
) -> list[str]:
    """造一波同 level + 同 club_type 的对照用户，每人 1 条完成态 analysis."""
    user_ids: list[str] = []
    for score in scores:
        uid = await _insert_user(golf_level=golf_level)
        await _insert_analysis(uid, overall_score=score, club_type=club_type)
        user_ids.append(uid)
    return user_ids


@pytest.mark.asyncio
async def test_score_percentile_below_min_cohort_returns_null():
    """W16-A · cohort_size 4 (< 5) → percentile/median = null（UI 隐藏）."""
    from app.core.database import AsyncSessionLocal

    level = _uniq_level()
    club = _uniq_club()
    # cohort 只有 4 人
    await _build_cohort(golf_level=level, club_type=club, scores=[60, 70, 80, 75])
    user_id = await _insert_user(golf_level=level)
    await _insert_analysis(user_id, overall_score=85, club_type=club)

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        resp = await get_user_score_percentile(db, user, club_type=club)

    assert resp.user_score == 85
    assert resp.cohort_size == 4
    assert resp.percentile is None
    assert resp.median is None


@pytest.mark.asyncio
async def test_score_percentile_user_beats_all():
    """W16-A · cohort 5 人全员 < user_score → percentile = 100."""
    from app.core.database import AsyncSessionLocal

    level = _uniq_level()
    club = _uniq_club()
    await _build_cohort(
        golf_level=level, club_type=club, scores=[60, 65, 70, 72, 75]
    )
    user_id = await _insert_user(golf_level=level)
    await _insert_analysis(user_id, overall_score=90, club_type=club)

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        resp = await get_user_score_percentile(db, user, club_type=club)

    assert resp.user_score == 90
    assert resp.cohort_size == 5
    assert resp.percentile == 100
    assert resp.median == 70  # [60,65,70,72,75] 中位数 70


@pytest.mark.asyncio
async def test_score_percentile_user_lowest():
    """W16-A · cohort 5 人全员 > user_score → percentile = 0."""
    from app.core.database import AsyncSessionLocal

    level = _uniq_level()
    club = _uniq_club()
    await _build_cohort(
        golf_level=level, club_type=club, scores=[80, 82, 85, 88, 90]
    )
    user_id = await _insert_user(golf_level=level)
    await _insert_analysis(user_id, overall_score=70, club_type=club)

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        resp = await get_user_score_percentile(db, user, club_type=club)

    assert resp.user_score == 70
    assert resp.cohort_size == 5
    assert resp.percentile == 0


@pytest.mark.asyncio
async def test_score_percentile_excludes_self():
    """W16-A · cohort 不能包含 user 自己（self-exclusion）.

    用户自己有多条完成态分析时，cohort_size 也只数同 level 的**其他**用户。
    """
    from app.core.database import AsyncSessionLocal

    level = _uniq_level()
    club = _uniq_club()
    await _build_cohort(
        golf_level=level, club_type=club, scores=[60, 65, 70, 75, 80]
    )
    user_id = await _insert_user(golf_level=level)
    # 用户本人插 3 条历史分析，最新一条得分 85
    await _insert_analysis(user_id, overall_score=50, club_type=club)
    await _insert_analysis(user_id, overall_score=70, club_type=club)
    await _insert_analysis(user_id, overall_score=85, club_type=club)

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        resp = await get_user_score_percentile(db, user, club_type=club)

    assert resp.user_score == 85  # 最新一条
    assert resp.cohort_size == 5  # 不含自己 3 条历史
    assert resp.percentile == 100  # 85 击败所有 [60,65,70,75,80]


@pytest.mark.asyncio
async def test_score_percentile_filters_by_club_type():
    """W16-A · cohort 严格按 club_type 过滤；不同杆型不混算."""
    from app.core.database import AsyncSessionLocal

    level = _uniq_level()
    club_a = _uniq_club()
    club_b = _uniq_club()
    # club_a cohort
    await _build_cohort(
        golf_level=level, club_type=club_a, scores=[60, 65, 70, 75, 80]
    )
    # club_b cohort（不该混进 club_a 查询）
    await _build_cohort(
        golf_level=level, club_type=club_b, scores=[40, 45, 50, 55, 60]
    )
    user_id = await _insert_user(golf_level=level)
    await _insert_analysis(user_id, overall_score=78, club_type=club_a)

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        resp = await get_user_score_percentile(db, user, club_type=club_a)

    # cohort_size 只数 club_a 的 5 人
    assert resp.cohort_size == 5
    assert resp.club_type == club_a


@pytest.mark.asyncio
async def test_score_percentile_filters_by_golf_level():
    """W16-A · cohort 严格按 golf_level 过滤；user 有 level 时不混级.

    用真实合法的两种 level（intermediate / advanced），unique club_type 隔离真数据.
    """
    from app.core.database import AsyncSessionLocal

    club = _uniq_club()
    # intermediate cohort（和 user 同级）
    await _build_cohort(
        golf_level="intermediate", club_type=club, scores=[60, 65, 70, 75, 80]
    )
    # advanced cohort（不该混进 intermediate 查询）
    await _build_cohort(
        golf_level="advanced", club_type=club, scores=[88, 90, 92, 95, 98]
    )
    user_id = await _insert_user(golf_level="intermediate")
    await _insert_analysis(user_id, overall_score=78, club_type=club)

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        resp = await get_user_score_percentile(db, user, club_type=club)

    assert resp.cohort_size == 5  # 只 intermediate 的 5 人
    assert resp.golf_level == "intermediate"
    assert "中级" in resp.cohort_label


@pytest.mark.asyncio
async def test_score_percentile_no_golf_level_means_all_levels():
    """W16-A · 用户没填 golf_level → cohort 不限定 level（"全部水平"）.

    用 unique club_type 隔离真数据 + 跨 2 个真实 level 凑 5 人 cohort。
    """
    from app.core.database import AsyncSessionLocal

    club = _uniq_club()
    await _build_cohort(golf_level="beginner", club_type=club, scores=[40, 45])
    await _build_cohort(
        golf_level="intermediate", club_type=club, scores=[60, 65, 70]
    )
    user_id = await _insert_user(golf_level=None)
    await _insert_analysis(user_id, overall_score=80, club_type=club)

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        resp = await get_user_score_percentile(db, user, club_type=club)

    assert resp.cohort_size == 5  # 跨 level 全 5 人
    assert resp.golf_level is None
    assert "全部水平" in resp.cohort_label


@pytest.mark.asyncio
async def test_score_percentile_no_user_analysis_returns_null_user_score():
    """W16-A · 用户没有任何同 club_type 完成态分析 → user_score=null."""
    from app.core.database import AsyncSessionLocal

    club = _uniq_club()
    await _build_cohort(
        golf_level="intermediate", club_type=club, scores=[60, 65, 70, 75, 80]
    )
    user_id = await _insert_user(golf_level="intermediate")
    # 故意不插任何 analysis

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        resp = await get_user_score_percentile(db, user, club_type=club)

    assert resp.user_score is None
    assert resp.percentile is None
    assert resp.median is None  # user_score=None 时不算 median
    assert resp.cohort_size == 5  # 但 cohort 仍然算


@pytest.mark.asyncio
async def test_score_percentile_excludes_sample_and_pending():
    """W16-A · cohort 不能算入 sample / 非完成态分析."""
    from app.core.database import AsyncSessionLocal

    club = _uniq_club()
    # 5 个有效 cohort 用户
    await _build_cohort(
        golf_level="intermediate", club_type=club, scores=[60, 65, 70, 75, 80]
    )
    # 再造 2 个 sample 用户 + 2 个 pending 用户（不该算）
    for score in [99, 99]:
        uid = await _insert_user(golf_level="intermediate")
        await _insert_analysis(uid, overall_score=score, club_type=club, is_sample=True)
    for _ in range(2):
        uid = await _insert_user(golf_level="intermediate")
        await _insert_analysis(uid, overall_score=99, club_type=club, status="pending")

    user_id = await _insert_user(golf_level="intermediate")
    await _insert_analysis(user_id, overall_score=70, club_type=club)

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        resp = await get_user_score_percentile(db, user, club_type=club)

    assert resp.cohort_size == 5  # sample/pending 都被过滤


@pytest.mark.asyncio
async def test_score_percentile_response_metadata():
    """W16-A · 响应 schema 校验：club_type 透传 + computed_at UTC + cohort_label 中文."""
    from app.core.database import AsyncSessionLocal

    club = _uniq_club()
    await _build_cohort(
        golf_level="intermediate", club_type=club, scores=[60, 65, 70, 75, 80]
    )
    user_id = await _insert_user(golf_level="intermediate")
    await _insert_analysis(user_id, overall_score=85, club_type=club)

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        resp = await get_user_score_percentile(db, user, club_type=club)

    # level 在 i18n 表中 → 走 "中级"；club 是 unique 不在表中 → 原样回显
    assert resp.cohort_label.startswith("中级 / ")
    assert resp.club_type == club
    assert resp.computed_at.tzinfo is not None  # timezone-aware
