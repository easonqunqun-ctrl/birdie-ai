"""P2-M9-02 装备清单 API + service 集成测试。

覆盖 kickoff §3.4 / §4.1：14 支上限 / 归属权校验 / CRUD 基础路径 + flag 守门。
依赖 M9-01 PR #90（UserClub ORM 模型 + Alembic 0017）。

使用现有 conftest fixtures：`client`（FastAPI ASGI）+ `auth_headers`（mock 登录）。
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.config import settings

pytestmark = pytest.mark.asyncio


# ============================================================
# 共享：开启 PHASE2 flag（kickoff §4.2）
# ============================================================


@pytest_asyncio.fixture(autouse=True)
async def _enable_profile_v2(monkeypatch: pytest.MonkeyPatch):
    """所有本文件测试默认开启 flag；individual test 可 monkeypatch 再关掉。"""
    monkeypatch.setattr(settings, "PHASE2_PROFILE_V2_ENABLED", True)


# ============================================================
# 0. Flag 守门
# ============================================================


async def test_clubs_endpoints_return_404_when_flag_disabled(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "PHASE2_PROFILE_V2_ENABLED", False)
    resp = await client.get("/v1/users/me/clubs", headers=auth_headers)
    assert resp.status_code == 404


# ============================================================
# 1. 空列表
# ============================================================


async def test_list_clubs_empty_for_new_user(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    resp = await client.get("/v1/users/me/clubs", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["items"] == []
    assert data["total"] == 0
    assert data["max_clubs"] == 14
    assert data["remaining"] == 14


# ============================================================
# 2. 添加 / 列表 / 删除 happy path
# ============================================================


async def test_add_list_delete_club_happy_path(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    # 添加 1 支
    resp = await client.post(
        "/v1/users/me/clubs",
        headers=auth_headers,
        json={"club_type": "iron_7", "nickname": "老搭子", "self_yardage_m": 140},
    )
    assert resp.status_code == 200, resp.text
    club = resp.json()["data"]
    club_id = club["id"]
    assert club_id.startswith("ucb_")
    assert club["club_type"] == "iron_7"
    assert club["nickname"] == "老搭子"

    # 列表显示 1 支
    resp = await client.get("/v1/users/me/clubs", headers=auth_headers)
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["remaining"] == 13
    assert data["items"][0]["id"] == club_id

    # 删除
    resp = await client.delete(f"/v1/users/me/clubs/{club_id}", headers=auth_headers)
    assert resp.status_code == 200

    # 列表空
    resp = await client.get("/v1/users/me/clubs", headers=auth_headers)
    assert resp.json()["data"]["total"] == 0


# ============================================================
# 3. PUT update_club
# ============================================================


async def test_update_club_partial(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    resp = await client.post(
        "/v1/users/me/clubs",
        headers=auth_headers,
        json={"club_type": "iron_7", "nickname": "A", "self_yardage_m": 120},
    )
    club_id = resp.json()["data"]["id"]

    # 仅改 nickname
    resp = await client.put(
        f"/v1/users/me/clubs/{club_id}",
        headers=auth_headers,
        json={"nickname": "B"},
    )
    assert resp.status_code == 200
    updated = resp.json()["data"]
    assert updated["nickname"] == "B"
    assert updated["club_type"] == "iron_7"  # 未传，保持
    assert updated["self_yardage_m"] == 120


# ============================================================
# 4. 14 支上限（AC-2）
# ============================================================


async def test_14_club_cap_returns_40020(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    for i in range(14):
        resp = await client.post(
            "/v1/users/me/clubs",
            headers=auth_headers,
            json={"club_type": "iron_7", "sort_order": i},
        )
        assert resp.status_code == 200, f"add #{i} failed: {resp.text}"

    # 第 15 支应被拒
    resp = await client.post(
        "/v1/users/me/clubs",
        headers=auth_headers,
        json={"club_type": "driver"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 40020


async def test_14_cap_resets_after_delete(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """删 1 支后回到 13/14，应能再加 1 支（R-04 兜底）。"""
    for i in range(14):
        await client.post(
            "/v1/users/me/clubs",
            headers=auth_headers,
            json={"club_type": "iron_7", "sort_order": i},
        )

    list_resp = await client.get("/v1/users/me/clubs", headers=auth_headers)
    first_id = list_resp.json()["data"]["items"][0]["id"]
    await client.delete(f"/v1/users/me/clubs/{first_id}", headers=auth_headers)

    # 加回 1 支应该 200
    resp = await client.post(
        "/v1/users/me/clubs",
        headers=auth_headers,
        json={"club_type": "driver"},
    )
    assert resp.status_code == 200


# ============================================================
# 5. 跨用户隔离 + 归属权
# ============================================================


async def test_clubs_are_user_isolated(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fresh_code,
):
    """另一用户的球杆不应出现在我的列表里。"""
    # 用户 A 加 1 支
    await client.post(
        "/v1/users/me/clubs",
        headers=auth_headers,
        json={"club_type": "iron_7"},
    )

    # 用户 B 登录
    resp_b = await client.post("/v1/auth/wechat-login", json={"code": fresh_code})
    token_b = resp_b.json()["data"]["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    list_b = await client.get("/v1/users/me/clubs", headers=headers_b)
    assert list_b.json()["data"]["total"] == 0


async def test_cannot_delete_another_users_club(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fresh_code,
):
    """删别人的球杆应 404。"""
    # 用户 A 加 1 支
    resp = await client.post(
        "/v1/users/me/clubs",
        headers=auth_headers,
        json={"club_type": "iron_7"},
    )
    a_club_id = resp.json()["data"]["id"]

    # 用户 B 登录
    resp_b = await client.post("/v1/auth/wechat-login", json={"code": fresh_code})
    token_b = resp_b.json()["data"]["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 用户 B 试图删用户 A 的球杆
    del_resp = await client.delete(
        f"/v1/users/me/clubs/{a_club_id}", headers=headers_b
    )
    assert del_resp.status_code == 404
    assert del_resp.json()["code"] == 40021


# ============================================================
# 6. 参数校验
# ============================================================


async def test_self_yardage_over_400_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    resp = await client.post(
        "/v1/users/me/clubs",
        headers=auth_headers,
        json={"club_type": "iron_7", "self_yardage_m": 500},
    )
    assert resp.status_code == 422  # Pydantic ValidationError


async def test_nickname_over_40_chars_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    resp = await client.post(
        "/v1/users/me/clubs",
        headers=auth_headers,
        json={"club_type": "iron_7", "nickname": "x" * 41},
    )
    assert resp.status_code == 422


async def test_unknown_club_type_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    resp = await client.post(
        "/v1/users/me/clubs",
        headers=auth_headers,
        json={"club_type": "garbage"},
    )
    assert resp.status_code == 422
