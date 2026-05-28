"""W6 ENG-A2 · /admin/engine-rollout 鉴权 + /metrics smoke 单测.

不引用真 ai_engine pipeline / mediapipe（用 FastAPI TestClient 直打 app 路由），
所以与 ai_engine-real 测试集互相隔离，可在普通 dev venv 跑。
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app import metrics, version_router
from app.main import app


@pytest.fixture(autouse=True)
def _isolate_state(monkeypatch):
    """每个用例前后都清 metrics + version_router 缓存，避免互相污染.

    关键：把 `M7_V2_ROLLOUT_PCT` env 显式清空 + `_redis_pct` 默认返回 0，
    避免在 CVM / 生产环境跑 pytest 时被实际的灰度配置污染（W5 时容器
    .env.local 里就有 ``M7_V2_ROLLOUT_PCT=5``，会让"基线 set(0) 不应被
    降级拦"这种用例假阳性）。
    """
    metrics.reset()
    version_router.invalidate_cache()
    monkeypatch.delenv("M7_V2_ROLLOUT_PCT", raising=False)
    monkeypatch.setattr(version_router, "_redis_pct", lambda: None)
    yield
    metrics.reset()
    version_router.invalidate_cache()


@pytest.fixture
def client():
    return TestClient(app)


# ---------- /metrics ----------


def test_metrics_endpoint_returns_baseline_shape(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.json()
    for k in (
        "rollout_pct",
        "mock_mode",
        "v1_count",
        "v2_count",
        "v1_errors",
        "v2_errors",
        "v2_fallback_count",
        "v2_traffic_ratio",
        "v1_avg_latency_ms",
        "v2_avg_latency_ms",
        "uptime_s",
    ):
        assert k in body, f"missing key in /metrics: {k}"
    assert body["v1_count"] == 0
    assert body["v2_count"] == 0


def test_metrics_reflects_recorded_counters(client):
    for _ in range(3):
        metrics.incr("v1_count")
    for _ in range(7):
        metrics.incr("v2_count")
    metrics.incr("v2_errors")

    body = client.get("/metrics").json()
    assert body["v1_count"] == 3
    assert body["v2_count"] == 7
    assert body["v2_errors"] == 1
    # traffic_ratio = 7/10 = 0.7
    assert body["v2_traffic_ratio"] == pytest.approx(0.7, rel=1e-3)
    assert body["v2_error_rate"] == pytest.approx(1 / 7, rel=1e-3)


# ---------- /admin/engine-rollout 鉴权 ----------


def _payload(pct: int, force: bool = False) -> dict:
    return {"pct": pct, "force": force}


def test_admin_rollout_no_token_required_when_env_unset(client, monkeypatch):
    monkeypatch.delenv("AI_ENGINE_ADMIN_TOKEN", raising=False)
    # 不带 X-Admin-Token；env 未配 → 200 + 正常返回
    resp = client.post("/admin/engine-rollout", json=_payload(0))
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


def test_admin_rollout_rejects_missing_token_when_env_set(client, monkeypatch):
    monkeypatch.setenv("AI_ENGINE_ADMIN_TOKEN", "s3cret")
    resp = client.post("/admin/engine-rollout", json=_payload(0))
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_admin_token"


def test_admin_rollout_rejects_wrong_token(client, monkeypatch):
    monkeypatch.setenv("AI_ENGINE_ADMIN_TOKEN", "s3cret")
    resp = client.post(
        "/admin/engine-rollout",
        json=_payload(0),
        headers={"X-Admin-Token": "wrong"},
    )
    assert resp.status_code == 401


def test_admin_rollout_accepts_correct_token(client, monkeypatch):
    monkeypatch.setenv("AI_ENGINE_ADMIN_TOKEN", "s3cret")
    resp = client.post(
        "/admin/engine-rollout",
        json=_payload(5),
        headers={"X-Admin-Token": "s3cret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["current_pct"] == 5


def test_admin_rollout_validates_pct_range(client, monkeypatch):
    monkeypatch.delenv("AI_ENGINE_ADMIN_TOKEN", raising=False)
    # >100 直接被 Pydantic 拦
    resp = client.post("/admin/engine-rollout", json={"pct": 150})
    assert resp.status_code == 422


def test_admin_rollout_downgrade_requires_force(client, monkeypatch):
    """test 环境无 Redis 时 set 不持久，所以 mock _redis_pct 假装 prev=50."""
    monkeypatch.delenv("AI_ENGINE_ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(version_router, "_redis_pct", lambda: 50)
    resp = client.post("/admin/engine-rollout", json=_payload(10, force=False))
    body = resp.json()
    assert body.get("code") == 40010
    assert body.get("confirm_required") is True


def test_admin_rollout_downgrade_with_force_succeeds(client, monkeypatch):
    monkeypatch.delenv("AI_ENGINE_ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(version_router, "_redis_pct", lambda: 50)
    resp = client.post("/admin/engine-rollout", json=_payload(10, force=True))
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["current_pct"] == 10
    assert body["data"]["downgrade"] is True
