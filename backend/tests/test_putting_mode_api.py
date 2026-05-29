"""M10-01 · POST /v1/analyses mode=putting 透传与灰度守门."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.fixture(autouse=True)
def enable_putting_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_PUTTING_MODE_ENABLED", True)


@pytest.mark.asyncio
async def test_create_analysis_putting_mode_persisted(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio,
):
    token_resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "putt.mp4",
            "file_size": 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 6.0,
        },
    )
    token_data = token_resp.json()["data"]
    fake_minio.mark_uploaded(token_data["key"], size=1024 * 1024)

    resp = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={
            "upload_id": token_data["upload_id"],
            "camera_angle": "face_on",
            "club_type": "putter",
            "mode": "putting",
        },
    )
    assert resp.status_code == 200, resp.text
    analysis_id = resp.json()["data"]["analysis_id"]

    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.analysis import SwingAnalysis

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(SwingAnalysis).where(SwingAnalysis.id == analysis_id))
        ).scalar_one()
        assert row.analysis_mode == "putting"


@pytest.mark.asyncio
async def test_create_analysis_putting_rejected_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "PHASE2_PUTTING_MODE_ENABLED", False)

    token_resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "putt.mp4",
            "file_size": 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 6.0,
        },
    )
    token_data = token_resp.json()["data"]
    fake_minio.mark_uploaded(token_data["key"], size=1024 * 1024)

    resp = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={
            "upload_id": token_data["upload_id"],
            "camera_angle": "face_on",
            "club_type": "putter",
            "mode": "putting",
        },
    )
    assert resp.status_code == 400


def test_build_putting_features_from_mode_scores():
    from app.models.analysis import SwingAnalysis
    from app.services.analysis_service import _build_putting_features

    analysis = SwingAnalysis(
        id="ana_test",
        user_id="usr_test",
        video_url="http://x/v.mp4",
        camera_angle="face_on",
        club_type="putter",
        analysis_mode="putting",
        mode_feature_scores={
            "pendulum_stability": 90,
            "head_stability": 70,
            "face_alignment": 80,
            "tempo_ratio": 85,
        },
    )
    feats = _build_putting_features(analysis)
    assert feats is not None
    assert feats["head_stability"].score == 70
    assert feats["head_stability"].is_weakest is True
    assert feats["pendulum_stability"].label == "钟摆稳定度"
