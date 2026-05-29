"""P2-M7-12 · /analyze mode=chipping 路由 + 50123 单测。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _body(**over) -> dict:
    base = {
        "analysis_id": "t-chip-1",
        "video_url": "http://example.com/v.mp4",
        "camera_angle": "face_on",
        "club_type": "wedge",
        "mode": "chipping",
    }
    base.update(over)
    return base


def test_chipping_mode_with_non_wedge_returns_50123(client) -> None:
    resp = client.post("/analyze", json=_body(club_type="driver"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["error_code"] == 50123


def test_chipping_mock_returns_chipping_report(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_ENGINE_MOCK_MODE", True)
    resp = client.post("/analyze", json=_body())
    data = resp.json()
    assert data["status"] == "completed"
    assert data["analysis_mode"] == "chipping"
    assert set(data["phase_scores"]) == {"setup", "backswing", "impact", "follow"}


def test_putting_mode_still_works(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_ENGINE_MOCK_MODE", True)
    resp = client.post(
        "/analyze",
        json={
            "analysis_id": "t-p",
            "video_url": "http://example.com/v.mp4",
            "camera_angle": "face_on",
            "club_type": "putter",
            "mode": "putting",
        },
    )
    assert resp.json()["analysis_mode"] == "putting"
