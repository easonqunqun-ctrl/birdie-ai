"""M13-03 邀请 API 测试：创建 + 撤回 + 我的列表."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.user import User
from tests.meetup_test_helpers import prepare_meetup_access


@pytest.fixture
def meetup_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_MEETUP_ENABLED", True)


@pytest.fixture
def meetup_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_MEETUP_ENABLED", False)


async def _make_other_user() -> str:
    async with AsyncSessionLocal() as db:
        u = User(
            id=new_id("usr"),
            wechat_openid=f"o_{new_id('mock')}",
            nickname="other",
            invite_code=new_id("inv")[-6:].upper(),
        )
        db.add(u)
        await db.commit()
        return u.id


@pytest.mark.asyncio
async def test_create_invitation_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_disabled: None,
) -> None:
    other_id = await _make_other_user()
    resp = await client.post(
        "/v1/meetups/invitations",
        json={"invitee_user_id": other_id},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_my_invitations_404_when_flag_off(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_disabled: None,
) -> None:
    resp = await client.get(
        "/v1/users/me/meetup-invitations", headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_and_list_invitation_round_trip(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    """A 给 B 发邀请 → A 在自己列表看到 (role=inviter, status=pending)."""

    other_id = await _make_other_user()
    await prepare_meetup_access(client, auth_headers)
    create_resp = await client.post(
        "/v1/meetups/invitations",
        json={"invitee_user_id": other_id, "message": "hi"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    inv_id = create_resp.json()["data"]["id"]

    list_resp = await client.get(
        "/v1/users/me/meetup-invitations?role=inviter",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    payload = list_resp.json()["data"]
    assert payload["role"] == "inviter"
    ids = {i["id"] for i in payload["items"]}
    assert inv_id in ids
    me = [i for i in payload["items"] if i["id"] == inv_id][0]
    assert me["status"] == "pending"
    assert me["invitee_user_id"] == other_id


@pytest.mark.asyncio
async def test_create_invitation_rejects_self(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    """给自己发邀请 → 40331（service 守门）.

    注：service 抛 BadRequestError → 客户端收到 400 + code=40331。
    """

    # 拿当前用户 id
    me = await client.get("/v1/users/me", headers=auth_headers)
    me_id = me.json()["data"]["id"]
    await prepare_meetup_access(client, auth_headers)
    resp = await client.post(
        "/v1/meetups/invitations",
        json={"invitee_user_id": me_id},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40331


@pytest.mark.asyncio
async def test_cancel_invitation_round_trip(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    """创建 → 撤回 → 列表显示 cancelled."""

    other_id = await _make_other_user()
    await prepare_meetup_access(client, auth_headers)
    create_resp = await client.post(
        "/v1/meetups/invitations",
        json={"invitee_user_id": other_id},
        headers=auth_headers,
    )
    inv_id = create_resp.json()["data"]["id"]

    cancel_resp = await client.post(
        f"/v1/meetups/invitations/{inv_id}/cancel", headers=auth_headers
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_list_status_filter(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    """status=cancelled 只返已撤回的."""

    other_id = await _make_other_user()
    await prepare_meetup_access(client, auth_headers)
    # 创建 + 撤回 1 个
    r1 = await client.post(
        "/v1/meetups/invitations",
        json={"invitee_user_id": other_id},
        headers=auth_headers,
    )
    await client.post(
        f"/v1/meetups/invitations/{r1.json()['data']['id']}/cancel",
        headers=auth_headers,
    )
    # 再发一个 pending
    r2 = await client.post(
        "/v1/meetups/invitations",
        json={"invitee_user_id": other_id},
        headers=auth_headers,
    )
    pending_id = r2.json()["data"]["id"]

    list_resp = await client.get(
        "/v1/users/me/meetup-invitations?role=inviter&status=cancelled",
        headers=auth_headers,
    )
    items = list_resp.json()["data"]["items"]
    statuses = {i["status"] for i in items}
    assert statuses == {"cancelled"}
    assert pending_id not in {i["id"] for i in items}
