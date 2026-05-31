"""P2-M7-13 · /detect-swings mock 模式路由单测."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_detect_swings_mock_mode(monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_ENGINE_MOCK_MODE", True)
    client = TestClient(app)
    resp = client.post(
        "/detect-swings",
        json={
            "analysis_id": "upl_test",
            "video_url": "http://example.com/video.mp4",
            "mode": "full_swing",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["swing_candidates"]) == 2
    assert data["default_selected_index"] == 1
    assert data["suggested_camera_angle"] == "face_on"
    assert data["detected_camera_angle"] == "face_on"
    assert data["camera_angle_confidence"] == 0.85
