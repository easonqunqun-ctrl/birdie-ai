"""M12-09 · 教练 video_ref 批注 API + service 测试."""

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
def coach_ann_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_ANNOTATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_PROS_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", True)


@pytest.fixture
def coach_ann_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COACH_ANNOTATIONS_ENABLED", False)


async def _seed_completed_analysis(*, user_id: str) -> str:
    analysis_id = new_id("ana")
    async with AsyncSessionLocal() as db:
        db.add(
            SwingAnalysis(
                id=analysis_id,
                user_id=user_id,
                status="completed",
                stage="completed",
                stage_progress=100,
                camera_angle="face_on",
                club_type="iron_7",
                video_url="https://x/v.mp4",
                video_duration=8.0,
                overall_score=80,
                created_at=datetime.now(UTC),
                analyzed_at=datetime.now(UTC),
            )
        )
        await db.commit()
    return analysis_id


@pytest.mark.asyncio
async def test_coach_annotation_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    coach_ann_disabled: None,
) -> None:
    resp = await client.get(
        "/v1/analyses/ana_x/coach-annotations",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_coach_video_ref_happy_path(
    client: AsyncClient,
    coach_ann_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"coach_ann_{new_id('x')[-10:]}"},
    )
    user_id = login.json()["data"]["user"]["id"]
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    monkeypatch.setattr(settings, "COACH_COURSE_USER_IDS", user_id)

    switch = await client.post(
        "/v1/auth/role-switch",
        json={"role": "coach"},
        headers=headers,
    )
    assert switch.status_code == 200, switch.text
    headers = {"Authorization": f"Bearer {switch.json()['data']['token']}"}

    analysis_id = await _seed_completed_analysis(user_id=user_id)
    async with AsyncSessionLocal() as db:
        players = await pro_svc.seed_initial_pros(db)
        clips = await pro_svc.list_published_clips(db, player_id=players[0].id)
        await db.commit()
        clip_id = clips[0].id

    create = await client.post(
        f"/v1/coach/analyses/{analysis_id}/annotations",
        headers=headers,
        json={"annotation_type": "video_ref", "pro_clip_id": clip_id},
    )
    assert create.status_code == 200
    assert create.json()["data"]["pro_clip_id"] == clip_id
    assert create.json()["data"]["clip"]["id"] == clip_id

    student_list = await client.get(
        f"/v1/analyses/{analysis_id}/coach-annotations",
        headers=headers,
    )
    assert student_list.status_code == 200
    assert len(student_list.json()["data"]) == 1
    assert student_list.json()["data"][0]["player"]["name"]

    me = await client.get("/v1/users/me", headers=headers)
    assert me.json()["data"]["can_coach_annotate"] is True
