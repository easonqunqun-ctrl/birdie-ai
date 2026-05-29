"""M12-04 GET /v1/analyses/{analysis_id}/pro-matches API 测试."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.services import pro_library_service as pro_svc


@pytest.fixture
def pros_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_PROS_ENABLED", True)


@pytest.fixture
def pros_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_PROS_ENABLED", False)


async def _current_user_id(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.get("/v1/users/me", headers=headers)
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


async def _seed_completed_analysis(
    *,
    user_id: str,
    overall_score: int = 85,
    club_type: str = "iron_7",
    camera_angle: str = "face_on",
) -> str:
    analysis_id = new_id("ana")
    async with AsyncSessionLocal() as db:
        db.add(
            SwingAnalysis(
                id=analysis_id,
                user_id=user_id,
                status="completed",
                stage="completed",
                stage_progress=100,
                camera_angle=camera_angle,
                club_type=club_type,
                video_url="https://x/v.mp4",
                video_duration=8.0,
                overall_score=overall_score,
                phase_scores={"setup": 84, "impact": 86},
                created_at=datetime.now(UTC),
                analyzed_at=datetime.now(UTC),
            )
        )
        await db.commit()
    return analysis_id


@pytest.mark.asyncio
async def test_pro_matches_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    pros_disabled: None,
) -> None:
    resp = await client.get("/v1/analyses/ana_any/pro-matches", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pro_matches_happy_path(
    client: AsyncClient,
    auth_headers: dict[str, str],
    pros_enabled: None,
) -> None:
    user_id = await _current_user_id(client, auth_headers)
    analysis_id = await _seed_completed_analysis(user_id=user_id)

    async with AsyncSessionLocal() as db:
        await pro_svc.seed_initial_pros(db)
        await db.commit()

    resp = await client.get(
        f"/v1/analyses/{analysis_id}/pro-matches?limit=3&record=true",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["analysis_id"] == analysis_id
    assert len(data["matches"]) >= 1
    top = data["matches"][0]
    assert "match_score" in top
    assert top["clip"]["club_type"] == "iron_7"
    assert top["player"]["name"]
    assert data["recorded_match_id"] is not None


@pytest.mark.asyncio
async def test_pro_matches_rejects_sample_analysis(
    client: AsyncClient,
    auth_headers: dict[str, str],
    pros_enabled: None,
) -> None:
    user_id = await _current_user_id(client, auth_headers)
    async with AsyncSessionLocal() as db:
        await pro_svc.seed_initial_pros(db)
        analysis_id = new_id("ana")
        db.add(
            SwingAnalysis(
                id=analysis_id,
                user_id=user_id,
                status="completed",
                camera_angle="face_on",
                club_type="iron_7",
                video_url="https://x/v.mp4",
                overall_score=80,
                is_sample=True,
            )
        )
        await db.commit()

    resp = await client.get(
        f"/v1/analyses/{analysis_id}/pro-matches",
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40093
