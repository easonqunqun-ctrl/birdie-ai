"""M10-03 · yardage book API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def enable_yardage_book(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_YARDAGE_BOOK_ENABLED", True)
    monkeypatch.setattr(settings, "PHASE2_PROFILE_V2_ENABLED", True)


async def test_yardage_book_put_self_yardage(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    club_resp = await client.post(
        "/v1/users/me/clubs",
        headers=auth_headers,
        json={"club_type": "iron_7", "nickname": "七号铁", "self_yardage_m": None},
    )
    assert club_resp.status_code == 200, club_resp.text
    club_id = club_resp.json()["data"]["id"]

    get_resp = await client.get("/v1/users/me/yardage-book", headers=auth_headers)
    assert get_resp.status_code == 200
    rows = get_resp.json()["data"]["clubs"]
    assert any(r["club_id"] == club_id for r in rows)

    put_resp = await client.put(
        "/v1/users/me/yardage-book",
        headers=auth_headers,
        json={"clubs": [{"club_id": club_id, "self_yardage_m": 155}]},
    )
    assert put_resp.status_code == 200, put_resp.text
    updated = put_resp.json()["data"]["clubs"]
    row = next(r for r in updated if r["club_id"] == club_id)
    assert row["my_yards"] == 155
    assert row["source"] == "self"
