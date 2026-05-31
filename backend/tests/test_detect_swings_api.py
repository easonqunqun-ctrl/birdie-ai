"""M7-13 · POST /v1/analyses/uploads/{id}/detect-swings."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.fakes import FakeAIEngine


@pytest.mark.asyncio
async def test_detect_swings_returns_candidates(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio,
    fake_ai_engine: FakeAIEngine,
    monkeypatch: pytest.MonkeyPatch,
):
    import app.integrations.ai_engine as ai_mod

    fake_ai_engine.detect_mode = "multi"
    monkeypatch.setattr(ai_mod, "get_ai_engine", lambda: fake_ai_engine)

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
        f"/v1/analyses/uploads/{token_data['upload_id']}/detect-swings",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["upload_id"] == token_data["upload_id"]
    assert len(data["swing_candidates"]) == 2
    assert data["default_selected_index"] == 1
    assert data["swing_candidates"][0].get("preview_frame_url")
    assert data["suggested_camera_angle"] == "face_on"
    assert data["detected_camera_angle"] == "face_on"
    assert data["camera_angle_confidence"] == 0.85
    assert any(c.get("method") == "detect_swings" for c in fake_ai_engine.calls)


@pytest.mark.asyncio
async def test_detect_swings_overflow_returns_50122(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio,
    fake_ai_engine: FakeAIEngine,
    monkeypatch: pytest.MonkeyPatch,
):
    import app.integrations.ai_engine as ai_mod

    fake_ai_engine.detect_mode = "overflow"
    monkeypatch.setattr(ai_mod, "get_ai_engine", lambda: fake_ai_engine)

    token_resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "many.mp4",
            "file_size": 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 20.0,
        },
    )
    token_data = token_resp.json()["data"]
    fake_minio.mark_uploaded(token_data["key"], size=1024 * 1024)

    resp = await client.post(
        f"/v1/analyses/uploads/{token_data['upload_id']}/detect-swings",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 50122


@pytest.mark.asyncio
async def test_detect_swings_requires_upload(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_ai_engine: FakeAIEngine,
    monkeypatch: pytest.MonkeyPatch,
):
    import app.integrations.ai_engine as ai_mod

    monkeypatch.setattr(ai_mod, "get_ai_engine", lambda: fake_ai_engine)

    token_resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "missing.mp4",
            "file_size": 512 * 1024,
            "file_type": "video/mp4",
            "duration": 5.0,
        },
    )
    token_data = token_resp.json()["data"]

    resp = await client.post(
        f"/v1/analyses/uploads/{token_data['upload_id']}/detect-swings",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40012
