"""M13-08 events API 测试."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.fixture
def meetup_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PHASE2_MEETUP_ENABLED", True)


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
async def test_list_event_templates(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    resp = await client.get("/v1/meetups/events/templates", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    codes = {item["code"] for item in body["data"]}
    assert codes == {"putting_contest", "distance_contest", "overall_score"}


@pytest.mark.asyncio
async def test_create_and_join_event_flow(
    client: AsyncClient,
    auth_headers: dict[str, str],
    meetup_enabled: None,
) -> None:
    create = await client.post(
        "/v1/meetups/events",
        json={
            "title": "周末推杆赛",
            "template_code": "putting_contest",
        },
        headers=auth_headers,
    )
    assert create.status_code == 200
    event_id = create.json()["data"]["id"]

    # join as current user
    join = await client.post(
        f"/v1/meetups/events/{event_id}/join",
        headers=auth_headers,
    )
    assert join.status_code == 200
    assert join.json()["data"]["participant_count"] == 1

    score = await client.post(
        f"/v1/meetups/events/{event_id}/submit-score",
        json={"self_reported_score": 8},
        headers=auth_headers,
    )
    assert score.status_code == 200
    assert score.json()["data"]["my_completion_badge"] is not None
    assert score.json()["data"]["leaderboard"][0]["self_reported_score"] == 8

    listing = await client.get("/v1/meetups/events?page=1", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] >= 1
