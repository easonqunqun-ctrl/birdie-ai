"""分析报告用户侧软删除（DELETE /v1/analyses/{id}）."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.analysis import AnalysisIssue, SwingAnalysis
from app.models.training import TrainingPlan
from app.services import training_service


async def _register(client: AsyncClient) -> dict:
    r = await client.post("/v1/auth/wechat-login", json={"code": f"pytest_{uuid4().hex}"})
    assert r.status_code == 200
    d = r.json()["data"]
    return {"token": d["token"], "user": d["user"], "headers": {"Authorization": f"Bearer {d['token']}"}}


async def _seed_analysis(
    *,
    user_id: str,
    status: str = "completed",
    is_sample: bool = False,
    overall_score: int | None = 78,
    with_issues: bool = False,
    analyzed_at: datetime | None = None,
) -> str:
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
            analyzed_at=analyzed_at or datetime.now(UTC),
        )
        db.add(analysis)
        await db.flush()
        if with_issues:
            db.add(
                AnalysisIssue(
                    id=new_id("iss"),
                    analysis_id=aid,
                    issue_type="casting",
                    name="抛杆",
                    severity="high",
                    description="测试",
                    sort_order=0,
                )
            )
        await db.commit()
    return aid


@pytest.mark.asyncio
async def test_soft_delete_completed_hides_from_list_and_detail(client: AsyncClient):
    u = await _register(client)
    aid = await _seed_analysis(user_id=u["user"]["id"], with_issues=True)

    rep = await client.get(f"/v1/analyses/{aid}", headers=u["headers"])
    assert rep.status_code == 200

    lst_before = await client.get("/v1/analyses", headers=u["headers"])
    assert lst_before.status_code == 200
    total_before = lst_before.json()["data"]["total"]

    del_r = await client.delete(f"/v1/analyses/{aid}", headers=u["headers"])
    assert del_r.status_code == 200, del_r.text
    assert del_r.json()["code"] == 0

    lst_after = await client.get("/v1/analyses", headers=u["headers"])
    assert lst_after.json()["data"]["total"] == total_before - 1

    gone = await client.get(f"/v1/analyses/{aid}", headers=u["headers"])
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_soft_delete_pending_returns_40092(client: AsyncClient):
    u = await _register(client)
    aid = await _seed_analysis(user_id=u["user"]["id"], status="pending", overall_score=None, analyzed_at=None)

    r = await client.delete(f"/v1/analyses/{aid}", headers=u["headers"])
    assert r.status_code == 400
    assert r.json()["code"] == 40092


@pytest.mark.asyncio
async def test_soft_delete_other_user_forbidden(client: AsyncClient):
    a = await _register(client)
    b = await _register(client)
    aid = await _seed_analysis(user_id=a["user"]["id"], with_issues=True)

    r = await client.delete(f"/v1/analyses/{aid}", headers=b["headers"])
    assert r.status_code == 403
    assert r.json()["code"] == 40301


@pytest.mark.asyncio
async def test_soft_delete_idempotent(client: AsyncClient):
    u = await _register(client)
    aid = await _seed_analysis(user_id=u["user"]["id"], with_issues=True)

    r1 = await client.delete(f"/v1/analyses/{aid}", headers=u["headers"])
    assert r1.status_code == 200
    r2 = await client.delete(f"/v1/analyses/{aid}", headers=u["headers"])
    assert r2.status_code == 200
    assert r2.json()["code"] == 0


@pytest.mark.asyncio
async def test_soft_delete_sample_row_returns_40093(client: AsyncClient):
    u = await _register(client)
    aid = await _seed_analysis(user_id=u["user"]["id"], is_sample=True, with_issues=True)

    r = await client.delete(f"/v1/analyses/{aid}", headers=u["headers"])
    assert r.status_code == 400
    assert r.json()["code"] == 40093


@pytest.mark.asyncio
async def test_public_report_404_when_soft_deleted(client: AsyncClient):
    u = await _register(client)
    aid = await _seed_analysis(user_id=u["user"]["id"], with_issues=True)

    pub_ok = await client.get(f"/v1/analyses/{aid}/public")
    assert pub_ok.status_code == 200

    await client.delete(f"/v1/analyses/{aid}", headers=u["headers"])

    pub_gone = await client.get(f"/v1/analyses/{aid}/public")
    assert pub_gone.status_code == 404


@pytest.mark.asyncio
async def test_soft_delete_clears_training_plan_source_analysis(client: AsyncClient, auth_headers: dict[str, str]):
    user_id = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]["id"]
    aid = await _seed_analysis(user_id=user_id, with_issues=True)

    async with AsyncSessionLocal() as db:
        plan = await training_service.generate_or_update_weekly(
            db,
            user_id=user_id,
            analysis_id=aid,
            issues=[{"type": "casting", "severity": "high"}],
        )
        await db.commit()
        assert plan is not None
        pid = plan.id

    del_r = await client.delete(f"/v1/analyses/{aid}", headers=auth_headers)
    assert del_r.status_code == 200, del_r.text

    async with AsyncSessionLocal() as db:
        plan_row = await db.get(TrainingPlan, pid)
        assert plan_row is not None
        assert plan_row.source_analysis_id is None
