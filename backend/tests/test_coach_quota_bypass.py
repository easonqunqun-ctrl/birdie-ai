"""M8-09 · 教练侧无配额（role bypass + 日限风控）."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError
from app.core.redis import get_redis
from app.core.security import new_id
from app.services import coach_abuse_service, quota_service
from app.services.user_service import get_user_by_id


@pytest.fixture
def coach_quota_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "COACH_QUOTA_BYPASS_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_COACH_ENABLED", True)
    monkeypatch.setattr(settings, "QUOTA_MODE", "strict")


async def _login(client: AsyncClient, *, suffix: str) -> tuple[str, dict[str, str]]:
    login = await client.post(
        "/v1/auth/wechat-login",
        json={"code": f"coach_quota_{suffix}"},
    )
    assert login.status_code == 200, login.text
    user_id = login.json()["data"]["user"]["id"]
    headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
    return user_id, headers


async def _approve_coach(
    client: AsyncClient,
    *,
    coach_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> dict[str, str]:
    apply = await client.post(
        "/v1/coach/profile/apply",
        json={
            "display_name": "配额教练",
            "level": "china_pga",
            "materials": [{"type": "cert", "object_key": "k1"}],
        },
        headers=coach_headers,
    )
    assert apply.status_code == 200, apply.text
    vid = apply.json()["data"]["latest_verification_id"]
    review = await client.post(
        f"/v1/admin/coach/verifications/{vid}/review",
        json={"decision": "approved"},
        headers=admin_headers,
    )
    assert review.status_code == 200, review.text
    switch = await client.post(
        "/v1/auth/role-switch",
        json={"role": "coach"},
        headers=coach_headers,
    )
    assert switch.status_code == 200, switch.text
    return {"Authorization": f"Bearer {switch.json()['data']['token']}"}


@pytest.mark.asyncio
async def test_coach_role_skips_analysis_and_chat_consume(
    client: AsyncClient,
    coach_quota_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-1：active 教练 + coach 角色不扣 DB quota."""
    coach_id, coach_headers = await _login(client, suffix=new_id("c")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("a")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    coach_headers = await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )

    redis = await get_redis()
    async with AsyncSessionLocal() as db:
        user = await get_user_by_id(db, coach_id)
        await quota_service.get_or_create_analysis_quota(db, user)
        await quota_service.get_or_create_chat_quota(db, user)
        await db.commit()

        user = await get_user_by_id(db, coach_id)
        for _ in range(3):
            await quota_service.consume_analysis_quota(
                db, user, request_role="coach", redis=redis
            )
            await quota_service.consume_chat_quota(
                db, user, request_role="coach", redis=redis
            )
        await db.commit()

        user = await get_user_by_id(db, coach_id)
        a_quota = await quota_service.get_or_create_analysis_quota(db, user)
        c_quota = await quota_service.get_or_create_chat_quota(db, user)
        assert a_quota.used == 0
        assert c_quota.used == 0


@pytest.mark.asyncio
async def test_user_role_still_consumes_after_coach_bypass(
    client: AsyncClient,
    coach_quota_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-2：同一 active 教练切回 user 后正常扣减."""
    coach_id, coach_headers = await _login(client, suffix=new_id("c2")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("a2")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    coach_headers = await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )

    redis = await get_redis()
    async with AsyncSessionLocal() as db:
        user = await get_user_by_id(db, coach_id)
        await quota_service.consume_analysis_quota(
            db, user, request_role="coach", redis=redis
        )
        await quota_service.consume_analysis_quota(
            db, user, request_role="user", redis=redis
        )
        await db.commit()

        user = await get_user_by_id(db, coach_id)
        quota = await quota_service.get_or_create_analysis_quota(db, user)
        assert quota.used == 1


@pytest.mark.asyncio
async def test_coach_daily_abuse_limit_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-3：超过 COACH_ANALYSIS_DAILY_LIMIT 后 fail closed."""
    monkeypatch.setattr(settings, "COACH_ANALYSIS_DAILY_LIMIT", 1)
    redis = await get_redis()
    user_id = new_id("usr")

    await coach_abuse_service.track_coach_quota_usage(
        redis, user_id=user_id, quota_type="analysis"
    )
    with pytest.raises(BadRequestError) as exc:
        await coach_abuse_service.track_coach_quota_usage(
            redis, user_id=user_id, quota_type="analysis"
        )
    assert exc.value.code == 40001


@pytest.mark.asyncio
async def test_coach_upload_token_does_not_reduce_remaining(
    client: AsyncClient,
    coach_quota_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, coach_headers = await _login(client, suffix=new_id("u")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("u2")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    coach_headers = await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )

    me0 = await client.get("/v1/users/me", headers=coach_headers)
    assert me0.json()["data"]["quota"]["analysis_remaining"] == 3

    payload = {
        "file_name": "swing.mp4",
        "file_size": 1024 * 1024,
        "file_type": "video/mp4",
        "duration": 8.0,
    }
    for _ in range(5):
        resp = await client.post(
            "/v1/analyses/upload-token",
            headers=coach_headers,
            json=payload,
        )
        assert resp.status_code == 200, resp.text

    me1 = await client.get("/v1/users/me", headers=coach_headers)
    assert me1.json()["data"]["quota"]["analysis_remaining"] == 3


@pytest.mark.asyncio
async def test_coach_chat_messages_skip_quota(
    client: AsyncClient,
    coach_quota_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, coach_headers = await _login(client, suffix=new_id("ch")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("ch2")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    coach_headers = await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )

    session = await client.post("/v1/chat/sessions", json={}, headers=coach_headers)
    sid = session.json()["data"]["session_id"]

    for i in range(6):
        resp = await client.post(
            f"/v1/chat/sessions/{sid}/messages",
            json={"content": f"coach tip {i}"},
            headers=coach_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["quota_remaining"] == 5

    me = await client.get("/v1/users/me", headers=coach_headers)
    assert me.json()["data"]["quota"]["chat_remaining_today"] == 5


@pytest.mark.asyncio
async def test_x_role_header_overrides_jwt_user(
    client: AsyncClient,
    coach_quota_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """X-Role: coach 优先于 JWT user claim（须 active 教练）."""
    _, coach_headers = await _login(client, suffix=new_id("xr")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("xr2")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )

    switch_user = await client.post(
        "/v1/auth/role-switch",
        json={"role": "user"},
        headers=coach_headers,
    )
    user_headers = {"Authorization": f"Bearer {switch_user.json()['data']['token']}"}
    coach_mode_headers = {**user_headers, "X-Role": "coach"}

    for _ in range(5):
        resp = await client.post(
            "/v1/analyses/upload-token",
            headers=coach_mode_headers,
            json={
                "file_name": "swing.mp4",
                "file_size": 1024 * 1024,
                "file_type": "video/mp4",
                "duration": 8.0,
            },
        )
        assert resp.status_code == 200, resp.text

    me = await client.get("/v1/users/me", headers=user_headers)
    assert me.json()["data"]["quota"]["analysis_remaining"] == 3


@pytest.mark.asyncio
async def test_check_then_consume_tracks_abuse_once(
    client: AsyncClient,
    coach_quota_enabled: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """upload-token 预检不计入日限；create 扣减时才 INCR 一次."""
    coach_id, coach_headers = await _login(client, suffix=new_id("once")[-8:])
    admin_id, admin_headers = await _login(client, suffix=new_id("once2")[-8:])
    monkeypatch.setattr(settings, "ADMIN_USER_IDS", admin_id)
    await _approve_coach(
        client, coach_headers=coach_headers, admin_headers=admin_headers
    )
    monkeypatch.setattr(settings, "COACH_ANALYSIS_DAILY_LIMIT", 1)

    redis = await get_redis()
    async with AsyncSessionLocal() as db:
        user = await get_user_by_id(db, coach_id)
        await quota_service.check_analysis_quota(
            db, user, request_role="coach", redis=redis
        )
        await quota_service.consume_analysis_quota(
            db, user, request_role="coach", redis=redis
        )
        with pytest.raises(BadRequestError) as exc:
            await quota_service.consume_analysis_quota(
                db, user, request_role="coach", redis=redis
            )
        assert exc.value.code == 40001
