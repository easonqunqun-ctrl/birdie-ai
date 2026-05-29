"""P2-M7-11 W25 · /analyze mode=putting 路由 + 50123 单测（TestClient，不跑真 pipeline）。"""

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
        "analysis_id": "t-putting-1",
        "video_url": "http://example.com/v.mp4",
        "camera_angle": "face_on",
        "club_type": "putter",
        "mode": "putting",
    }
    base.update(over)
    return base


def test_putting_mode_with_non_putter_returns_50123(client) -> None:
    resp = client.post("/analyze", json=_body(club_type="driver"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["error_code"] == 50123
    assert data["analysis_mode"] == "putting"


def test_full_swing_mode_with_putter_returns_50123(client) -> None:
    resp = client.post("/analyze", json=_body(mode="full_swing", club_type="putter"))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["error_code"] == 50123


def test_putting_mock_returns_putting_report(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_ENGINE_MOCK_MODE", True)
    resp = client.post("/analyze", json=_body())
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["analysis_mode"] == "putting"
    assert set(data["phase_scores"]) == {"setup", "backstroke", "impact", "follow"}


def test_full_swing_default_unaffected(client, monkeypatch) -> None:
    """默认 mode=full_swing + 非推杆球杆 → 走原 mock 全挥杆链路，analysis_mode=full_swing。"""
    monkeypatch.setattr(settings, "AI_ENGINE_MOCK_MODE", True)
    body = {
        "analysis_id": "t-fs-1",
        "video_url": "http://example.com/v.mp4",
        "camera_angle": "face_on",
        "club_type": "iron_7",
    }
    resp = client.post("/analyze", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["analysis_mode"] == "full_swing"
