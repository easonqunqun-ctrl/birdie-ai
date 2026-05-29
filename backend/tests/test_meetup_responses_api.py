"""M13-04 邀请响应 API 测试：accept / decline 端点 + contact 守门."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.meetup import MeetupInvitation
from app.models.user import User
from tests.meetup_test_helpers import prepare_meetup_access


@pytest.fixture
def meetup_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_MEETUP_ENABLED", True)


@pytest.fixture
def meetup_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_MEETUP_ENABLED", False)


async def _make_invitation_for_user(invitee_user_id: str) -> tuple[str, str]:
    """A 给目标 user 发一条 pending 邀请，返回 (invitation_id, inviter_id)."""

    async with AsyncSessionLocal() as db:
        inviter = User(
            id=new_id("usr"),
            wechat_openid=f"o_{new_id('mock')}",
            nickname="inviter",
            invite_code=new_id("inv")[-6:].upper(),
        )
        db.add(inviter)
        await db.flush()
        inv = MeetupInvitation(
            id=new_id("mvi"),
            inviter_user_id=inviter.id,
            invitee_user_id=invitee_user_id,
            status="pending",
        )
        db.add(inv)
        await db.commit()
        return inv.id, inviter.id


async def _current_user_id(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.get("/v1/users/me", headers=headers)
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_accept_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_disabled: None,
) -> None:
    resp = await client.post(
        "/v1/meetups/invitations/anything/accept", headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_decline_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_disabled: None,
) -> None:
    resp = await client.post(
        "/v1/meetups/invitations/anything/decline", headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_accept_happy_path_with_contact(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    me_id = await _current_user_id(client, auth_headers)
    inv_id, _ = await _make_invitation_for_user(me_id)
    await prepare_meetup_access(client, auth_headers)

    resp = await client.post(
        f"/v1/meetups/invitations/{inv_id}/accept",
        json={"note": "见面在练习场门口"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == "accepted"
    assert body["accepted_at"] is not None
    # invitee 是当事人 → contact_payload 不被屏蔽
    assert body["contact_payload"] is not None
    assert body["contact_payload"].get("note") == "见面在练习场门口"


@pytest.mark.asyncio
async def test_accept_rejects_non_invitee(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    """另一个用户 X（既不是 inviter 也不是 invitee）尝试 accept → 40330."""

    # 当前用户作为 invitee；造一条针对 *其他人* 的邀请，当前用户尝试 accept
    other_invitee = User(
        id=new_id("usr"),
        wechat_openid=f"o_{new_id('mock')}",
        nickname="other",
        invite_code=new_id("inv")[-6:].upper(),
    )
    async with AsyncSessionLocal() as db:
        db.add(other_invitee)
        await db.commit()
    inv_id, _ = await _make_invitation_for_user(other_invitee.id)
    await prepare_meetup_access(client, auth_headers)

    resp = await client.post(
        f"/v1/meetups/invitations/{inv_id}/accept", headers=auth_headers
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 40330


@pytest.mark.asyncio
async def test_accept_rejects_contact_with_phone(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    """contact_payload extra='forbid'：手机号 / openid / wx_xxx 一律 422."""

    me_id = await _current_user_id(client, auth_headers)
    inv_id, _ = await _make_invitation_for_user(me_id)
    await prepare_meetup_access(client, auth_headers)

    resp = await client.post(
        f"/v1/meetups/invitations/{inv_id}/accept",
        json={"note": "找我", "phone": "13800001111"},
        headers=auth_headers,
    )
    # Pydantic extra='forbid' → 422
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_decline_happy_path(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    me_id = await _current_user_id(client, auth_headers)
    inv_id, _ = await _make_invitation_for_user(me_id)
    await prepare_meetup_access(client, auth_headers)

    resp = await client.post(
        f"/v1/meetups/invitations/{inv_id}/decline", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "declined"


@pytest.mark.asyncio
async def test_accept_idempotency_via_status_check(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    """第二次 accept 同一邀请 → 40903 (非 pending)."""

    me_id = await _current_user_id(client, auth_headers)
    inv_id, _ = await _make_invitation_for_user(me_id)
    await prepare_meetup_access(client, auth_headers)
    r1 = await client.post(
        f"/v1/meetups/invitations/{inv_id}/accept", headers=auth_headers
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/v1/meetups/invitations/{inv_id}/accept", headers=auth_headers
    )
    assert r2.status_code == 400
    assert r2.json()["code"] == 40903
