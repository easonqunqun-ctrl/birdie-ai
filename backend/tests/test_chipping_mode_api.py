"""M10-02 · chipping mode API tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.fixture(autouse=True)
def enable_chipping_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_CHIPPING_MODE_ENABLED", True)


def test_build_chipping_features_from_mode_scores():
    from app.models.analysis import SwingAnalysis
    from app.services.analysis_service import _build_chipping_features

    analysis = SwingAnalysis(
        id="ana_chip",
        user_id="usr_test",
        video_url="http://x/v.mp4",
        camera_angle="face_on",
        club_type="wedge",
        analysis_mode="chipping",
        mode_feature_scores={
            "half_swing_amplitude": 75,
            "face_open_angle": 82,
            "contact_point_quality": 88,
        },
    )
    feats = _build_chipping_features(analysis)
    assert feats is not None
    assert feats["half_swing_amplitude"].score == 75
    assert feats["half_swing_amplitude"].is_weakest is True


@pytest.mark.asyncio
async def test_create_analysis_chipping_mode_persisted(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio,
):
    token_resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "chip.mp4",
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
            "club_type": "wedge",
            "mode": "chipping",
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
        assert row.analysis_mode == "chipping"
