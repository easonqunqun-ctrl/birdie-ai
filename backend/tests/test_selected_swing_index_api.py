"""M7-13 · POST /v1/analyses selected_swing_index 透传与守门."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.analysis import SwingAnalysis


@pytest.mark.asyncio
async def test_create_analysis_selected_swing_index_persisted(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio,
):
    token_resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "multi.mp4",
            "file_size": 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 12.0,
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
            "club_type": "iron_7",
            "mode": "full_swing",
            "selected_swing_index": 2,
        },
    )
    assert resp.status_code == 200, resp.text
    analysis_id = resp.json()["data"]["analysis_id"]

    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(SwingAnalysis).where(SwingAnalysis.id == analysis_id))
        ).scalar_one()
        assert row.selected_swing_index == 2


@pytest.mark.asyncio
async def test_create_analysis_selected_swing_index_rejected_for_putting(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "PHASE2_PUTTING_MODE_ENABLED", True)

    token_resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "putt.mp4",
            "file_size": 512 * 1024,
            "file_type": "video/mp4",
            "duration": 5.0,
        },
    )
    token_data = token_resp.json()["data"]
    fake_minio.mark_uploaded(token_data["key"], size=512 * 1024)

    resp = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={
            "upload_id": token_data["upload_id"],
            "camera_angle": "face_on",
            "club_type": "putter",
            "mode": "putting",
            "selected_swing_index": 0,
        },
    )
    assert resp.status_code == 400
    assert "全挥杆" in resp.json()["message"]
