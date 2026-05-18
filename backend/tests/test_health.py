"""健康检查与登录链路 smoke test."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert resp.status_code == 200
    assert resp.json()["name"] == "xiaoniao-ai-backend"


@pytest.mark.asyncio
async def test_health_endpoint_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/v1/health")
    # 即便 db/redis/ai_engine 未连上，接口本身应返回 200 + degraded
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "services" in body
    assert "ai_engine" in body["services"]
    assert "ai_engine" in body
    assert isinstance(body["ai_engine"], dict)
