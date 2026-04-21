"""W7-T5：分享报告 + 埋点 测试.

覆盖：
- POST /shares/log 成功 → 落库
- POST /shares/log 非法 share_type → 422
- GET /analyses/{id}/public 成功（自己的分析）
- GET /analyses/{id}/public 对 is_sample=True → 404
- GET /analyses/{id}/public 对 status!=completed → 404
- GET /analyses/{id}/public 对不存在 ID → 404
- 公开报告只含 high/medium issue（最多 3 条）+ 脱敏昵称
- /public 无需 Authorization 头
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.analysis import AnalysisIssue, SwingAnalysis
from app.models.share import ShareAction
from app.models.user import User


async def _register(client: AsyncClient) -> dict:
    r = await client.post(
        "/v1/auth/wechat-login", json={"code": f"pytest_{uuid4().hex}"}
    )
    assert r.status_code == 200
    d = r.json()["data"]
    return {
        "token": d["token"],
        "user": d["user"],
        "headers": {"Authorization": f"Bearer {d['token']}"},
    }


async def _seed_analysis(
    *,
    user_id: str,
    status: str = "completed",
    is_sample: bool = False,
    overall_score: int | None = 78,
    issues: list[tuple[str, str, str]] | None = None,
) -> str:
    """issues: [(type, name, severity), ...]."""
    aid = new_id("ana")
    async with AsyncSessionLocal() as db:
        analysis = SwingAnalysis(
            id=aid,
            user_id=user_id,
            video_url="s3://fake/v.mp4",
            video_file_size=1024,
            camera_angle="face_on",
            club_type="driver",
            status=status,  # type: ignore[arg-type]
            is_sample=is_sample,
            overall_score=overall_score,
            thumbnail_url="https://cdn.example.com/thumb.jpg",
        )
        db.add(analysis)
        await db.flush()

        for i, (t, n, sev) in enumerate(issues or []):
            db.add(
                AnalysisIssue(
                    id=new_id("iss"),
                    analysis_id=aid,
                    issue_type=t,
                    name=n,
                    severity=sev,
                    description=f"{n} 的详细描述",
                    sort_order=i,
                )
            )
        await db.commit()
    return aid


# ==================== 埋点 ====================
@pytest.mark.asyncio
async def test_log_share_creates_row(client: AsyncClient):
    u = await _register(client)
    aid = await _seed_analysis(user_id=u["user"]["id"])

    r = await client.post(
        "/v1/shares/log",
        headers=u["headers"],
        json={"share_type": "report", "target_id": aid},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["share_type"] == "report"
    assert data["id"].startswith("sha_")

    async with AsyncSessionLocal() as db:
        count = (
            await db.execute(
                select(func.count())
                .select_from(ShareAction)
                .where(ShareAction.user_id == u["user"]["id"])
            )
        ).scalar_one()
        assert count == 1


@pytest.mark.asyncio
async def test_log_share_rejects_invalid_type(client: AsyncClient):
    u = await _register(client)
    r = await client.post(
        "/v1/shares/log",
        headers=u["headers"],
        json={"share_type": "friend_circle", "target_id": None},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_log_share_requires_auth(client: AsyncClient):
    r = await client.post(
        "/v1/shares/log", json={"share_type": "report", "target_id": "ana_x"}
    )
    assert r.status_code == 401


# ==================== 公开报告 ====================
@pytest.mark.asyncio
async def test_public_report_strips_sensitive_fields(client: AsyncClient):
    u = await _register(client)
    # 设个昵称验证脱敏
    async with AsyncSessionLocal() as db:
        user = await db.get(User, u["user"]["id"])
        user.nickname = "小李飞刀"
        await db.commit()

    aid = await _seed_analysis(
        user_id=u["user"]["id"],
        issues=[
            ("casting", "抛杆", "high"),
            ("chicken_wing", "鸡翅", "medium"),
            ("over_the_top", "越顶", "low"),  # low 会被过滤
            ("reverse_pivot", "反向轴移", "high"),
            ("sway", "晃动", "medium"),  # 第 4 条同级，会被 limit=3 截断
        ],
    )

    # 无 Authorization 头也能访问
    r = await client.get(f"/v1/analyses/{aid}/public")
    assert r.status_code == 200
    data = r.json()["data"]

    assert data["id"] == aid
    assert data["overall_score"] == 78
    assert data["score_level"] is not None
    assert data["thumbnail_url"] == "https://cdn.example.com/thumb.jpg"
    assert data["club_type"] == "driver"
    assert data["owner_nickname_masked"] == "小***刀"

    # 只有 high/medium、最多 3 条
    assert len(data["issues"]) == 3
    severities = {i["severity"] for i in data["issues"]}
    assert "low" not in severities
    # 总数字段包含全部（5 条）
    assert data["issues_total"] == 5

    # 确保敏感字段不在响应里
    assert "recommendations" not in data
    assert "skeleton_video_url" not in data
    assert "skeleton_data_url" not in data
    assert "phase_scores" not in data
    assert "user_id" not in data  # 换成脱敏昵称


@pytest.mark.asyncio
async def test_public_report_404_for_sample(client: AsyncClient):
    u = await _register(client)
    aid = await _seed_analysis(user_id=u["user"]["id"], is_sample=True)
    r = await client.get(f"/v1/analyses/{aid}/public")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_public_report_404_for_unfinished(client: AsyncClient):
    u = await _register(client)
    aid = await _seed_analysis(user_id=u["user"]["id"], status="processing")
    r = await client.get(f"/v1/analyses/{aid}/public")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_public_report_404_for_missing(client: AsyncClient):
    r = await client.get("/v1/analyses/ana_nonexistent/public")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_public_report_anonymous_owner(client: AsyncClient):
    """分享者没有昵称 → 显示'匿名球友'."""
    u = await _register(client)
    aid = await _seed_analysis(user_id=u["user"]["id"])
    r = await client.get(f"/v1/analyses/{aid}/public")
    assert r.status_code == 200
    assert r.json()["data"]["owner_nickname_masked"] == "匿名球友"
