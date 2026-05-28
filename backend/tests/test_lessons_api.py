"""P2-M11-04 POST /v1/lessons/{lesson_id}/attempt 集成测试."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.schemas.course import CourseCreate, LessonCreate
from app.services import course_service as svc


@pytest.fixture
def courses_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COURSES_ENABLED", True)


@pytest.fixture
def courses_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_COURSES_ENABLED", False)


async def _current_user_id(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.get("/v1/users/me", headers=headers)
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


async def _seed_assessment_lesson(
    *,
    user_id: str,
    min_score: int = 80,
) -> tuple[str, str]:
    async with AsyncSessionLocal() as db:
        course = await svc.create_course(
            db,
            CourseCreate(
                code=f"assess_{new_id('x')[-6:]}",
                title="Assessment Course",
                stage=1,
            ),
        )
        lesson = await svc.create_lesson(
            db,
            LessonCreate(
                course_id=course.id,
                code=f"lsn_assess_{new_id('x')[-6:]}",
                title="Stage check",
                sort_order=1,
                pass_criteria={
                    "type": "engine_score",
                    "engine_mode": "drive",
                    "min_score": min_score,
                    "max_attempts_per_day": 3,
                },
            ),
        )
        await svc.publish_course(db, course.id)
        analysis_id = new_id("swa")
        db.add(
            SwingAnalysis(
                id=analysis_id,
                user_id=user_id,
                video_url="s3://fake/video.mp4",
                video_file_size=1024,
                camera_angle="face_on",
                club_type="driver",
                status="completed",
                overall_score=85,
            )
        )
        await db.commit()
        return lesson.id, analysis_id


@pytest.mark.asyncio
async def test_lesson_attempt_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    courses_disabled: None,
) -> None:
    resp = await client.post(
        "/v1/lessons/lsn_any/attempt",
        headers=auth_headers,
        json={"swing_analysis_id": "swa_any"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_lesson_attempt_passes_with_completed_analysis(
    client: AsyncClient,
    auth_headers: dict[str, str],
    courses_enabled: None,
) -> None:
    user_id = await _current_user_id(client, auth_headers)
    lesson_id, analysis_id = await _seed_assessment_lesson(user_id=user_id, min_score=80)

    resp = await client.post(
        f"/v1/lessons/{lesson_id}/attempt",
        headers=auth_headers,
        json={"swing_analysis_id": analysis_id},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["passed"] is True
    assert data["score"] == 85
    assert data["min_score"] == 80
    assert data["attempts_used"] == 1


@pytest.mark.asyncio
async def test_lesson_attempt_fails_when_score_below_threshold(
    client: AsyncClient,
    auth_headers: dict[str, str],
    courses_enabled: None,
) -> None:
    user_id = await _current_user_id(client, auth_headers)
    lesson_id, analysis_id = await _seed_assessment_lesson(user_id=user_id, min_score=90)

    resp = await client.post(
        f"/v1/lessons/{lesson_id}/attempt",
        headers=auth_headers,
        json={"swing_analysis_id": analysis_id},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["passed"] is False
    assert data["failure_reason"] == "score_below_threshold"


@pytest.mark.asyncio
async def test_lesson_attempt_rejects_engine_mode_mismatch(
    client: AsyncClient,
    auth_headers: dict[str, str],
    courses_enabled: None,
) -> None:
    user_id = await _current_user_id(client, auth_headers)
    async with AsyncSessionLocal() as db:
        course = await svc.create_course(
            db,
            CourseCreate(
                code=f"assess_putt_{new_id('x')[-6:]}",
                title="Putting check",
                stage=1,
            ),
        )
        lesson = await svc.create_lesson(
            db,
            LessonCreate(
                course_id=course.id,
                code=f"lsn_putt_{new_id('x')[-6:]}",
                title="Putting",
                sort_order=1,
                pass_criteria={
                    "type": "engine_score",
                    "engine_mode": "putting",
                    "min_score": 70,
                },
            ),
        )
        await svc.publish_course(db, course.id)
        analysis_id = new_id("swa")
        db.add(
            SwingAnalysis(
                id=analysis_id,
                user_id=user_id,
                video_url="s3://fake/video.mp4",
                video_file_size=1024,
                camera_angle="face_on",
                club_type="driver",
                status="completed",
                overall_score=95,
            )
        )
        await db.commit()
        lesson_id = lesson.id

    resp = await client.post(
        f"/v1/lessons/{lesson_id}/attempt",
        headers=auth_headers,
        json={"swing_analysis_id": analysis_id},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["passed"] is False
    assert data["failure_reason"] == "engine_mode_mismatch"
