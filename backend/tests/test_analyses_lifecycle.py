"""M2-T1 分析任务 API 骨架的集成测试。

覆盖：
- POST /v1/analyses/upload-token：规格/配额预检、正常路径。
- POST /v1/analyses：upload_id 不存在/不属于自己/对象未上传/正常扣配额。
- GET /v1/analyses/{id}/status：pending 状态。
- GET /v1/analyses/{id}：尚未完成时 409。
- GET /v1/analyses：分页 + 按 club_type 筛选 + 过滤 is_sample。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.fakes import FakeMinioStorage


@pytest.mark.asyncio
async def test_upload_token_rejects_oversized_file(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """文件超过 100MB 应拒绝（40005）。"""
    resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "big.mp4",
            "file_size": 150 * 1024 * 1024,  # 150MB
            "file_type": "video/mp4",
            "duration": 10.0,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40005


@pytest.mark.asyncio
async def test_upload_token_rejects_too_short_duration(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """时长 < 3s 应拒绝（40004）。"""
    resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "short.mp4",
            "file_size": 1024,
            "file_type": "video/mp4",
            "duration": 1.5,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40004


@pytest.mark.asyncio
async def test_upload_token_happy_path_returns_fields(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """正常签发凭证：返回 upload_id / upload_url / fields / key / expires_at。"""
    resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "swing.mp4",
            "file_size": 10 * 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 12.5,
        },
    )
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    assert data["upload_id"].startswith("upl_")
    assert data["upload_url"].startswith("http://localhost:9000/")
    assert data["key"].startswith("uploads/")
    assert data["key"].endswith(".mp4")
    assert "policy" in data["fields"]
    assert data["fields"]["x-amz-algorithm"] == "AWS4-HMAC-SHA256"
    assert data["max_file_size"] == 100 * 1024 * 1024


@pytest.mark.asyncio
async def test_upload_video_via_api_gateway_then_create(
    client: AsyncClient, auth_headers: dict[str, str], fake_minio: FakeMinioStorage
):
    """小程序同源兜底：POST multipart 至 /uploads/{id}/video 写入存储后可创建任务。"""
    blob = b"fake-mp4-bytes-" + b"x" * 2048
    token_resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "swing.mp4",
            "file_size": len(blob),
            "file_type": "video/mp4",
            "duration": 8.0,
        },
    )
    assert token_resp.status_code == 200, token_resp.text
    upload_id = token_resp.json()["data"]["upload_id"]
    key = token_resp.json()["data"]["key"]

    up = await client.post(
        f"/v1/analyses/uploads/{upload_id}/video",
        headers=auth_headers,
        files={"file": ("swing.mp4", blob, "video/mp4")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["code"] == 0

    stat = fake_minio.head_object(key)
    assert stat is not None
    assert stat["size"] == len(blob)

    resp = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={
            "upload_id": upload_id,
            "camera_angle": "face_on",
            "club_type": "iron_7",
        },
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_create_analysis_rejects_unknown_upload_id(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """upload_id 不存在 → 40011。"""
    resp = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={
            "upload_id": "upl_nonexistent",
            "camera_angle": "face_on",
            "club_type": "driver",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40011


@pytest.mark.asyncio
async def test_create_analysis_rejects_corrupted_upload_token_payload(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
):
    """Redis 凭证 JSON 损坏时不应裸 500，而应视为凭证无效（40011）。"""
    token_resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "swing.mp4",
            "file_size": 5 * 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 8.0,
        },
    )
    assert token_resp.status_code == 200, token_resp.text
    upload_id = token_resp.json()["data"]["upload_id"]
    key = token_resp.json()["data"]["key"]
    fake_minio.mark_uploaded(key, 5 * 1024 * 1024)

    from app.core.redis import get_redis
    from app.services.analysis_service import UPLOAD_TOKEN_REDIS_KEY

    redis = await get_redis()
    await redis.set(
        UPLOAD_TOKEN_REDIS_KEY.format(upload_id=upload_id),
        "not-valid-json{{{",
    )

    resp = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={
            "upload_id": upload_id,
            "camera_angle": "face_on",
            "club_type": "driver",
        },
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == 40011


@pytest.mark.asyncio
async def test_create_analysis_rejects_missing_object(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
):
    """凭证合法但对象没真正传上 MinIO → 40012。"""
    token_resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "swing.mp4",
            "file_size": 5 * 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 8.0,
        },
    )
    upload_id = token_resp.json()["data"]["upload_id"]

    resp = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={
            "upload_id": upload_id,
            "camera_angle": "face_on",
            "club_type": "iron_7",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40012


@pytest.mark.asyncio
async def test_create_analysis_happy_path_consumes_quota(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
):
    """正常创建任务：扣减配额 1 次，状态 pending，返回队列位置。"""
    # 配额预检查
    me_before = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    remaining_before = me_before["quota"]["analysis_remaining"]

    token_resp = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "swing.mp4",
            "file_size": 5 * 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 8.0,
        },
    )
    token_data = token_resp.json()["data"]
    fake_minio.mark_uploaded(token_data["key"], size=5 * 1024 * 1024)

    resp = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={
            "upload_id": token_data["upload_id"],
            "camera_angle": "face_on",
            "club_type": "iron_7",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["analysis_id"].startswith("ana_")
    assert body["status"] == "pending"
    assert body["estimated_seconds"] > 0

    # 配额应该 -1
    me_after = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me_after["quota"]["analysis_remaining"] == remaining_before - 1

    # 同一个 upload_id 不能再次用
    repeat = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={
            "upload_id": token_data["upload_id"],
            "camera_angle": "face_on",
            "club_type": "iron_7",
        },
    )
    assert repeat.status_code == 400
    assert repeat.json()["code"] == 40011


@pytest.mark.asyncio
async def test_status_pending_and_report_conflict(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
):
    """创建完任务后：/status 返回 pending；/（report）返回 409。"""
    # 创建
    t = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "swing.mp4",
            "file_size": 3 * 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 5.0,
        },
    )
    token = t.json()["data"]
    fake_minio.mark_uploaded(token["key"], size=3 * 1024 * 1024)
    r = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={
            "upload_id": token["upload_id"],
            "camera_angle": "down_the_line",
            "club_type": "driver",
        },
    )
    analysis_id = r.json()["data"]["analysis_id"]

    # status
    s = await client.get(f"/v1/analyses/{analysis_id}/status", headers=auth_headers)
    assert s.status_code == 200
    sdata = s.json()["data"]
    assert sdata["status"] == "pending"
    assert sdata["stage"] is None
    assert sdata["estimated_remaining_seconds"] > 0

    # report 未完成 → 409
    rep = await client.get(f"/v1/analyses/{analysis_id}", headers=auth_headers)
    assert rep.status_code == 409
    assert rep.json()["code"] == 40904


@pytest.mark.asyncio
async def test_cross_user_upload_id_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
):
    """A 用户的 upload_id 不能被 B 用户创建分析。"""
    # A 拿 token
    t = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "a.mp4",
            "file_size": 2 * 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 6.0,
        },
    )
    token_a = t.json()["data"]
    fake_minio.mark_uploaded(token_a["key"], size=2 * 1024 * 1024)

    # 注册 B 用户
    login_b = await client.post(
        "/v1/auth/wechat-login", json={"code": "pytest_other_user_xxxx"}
    )
    token_b_jwt = login_b.json()["data"]["token"]
    headers_b = {"Authorization": f"Bearer {token_b_jwt}"}

    # B 用 A 的 upload_id → 40011
    r = await client.post(
        "/v1/analyses",
        headers=headers_b,
        json={
            "upload_id": token_a["upload_id"],
            "camera_angle": "face_on",
            "club_type": "driver",
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == 40011


@pytest.mark.asyncio
async def test_list_analyses_pagination_and_filter(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
):
    """创建 3 条不同 club_type 的任务，验证分页 + club_type 筛选。"""
    clubs = ["driver", "iron_7", "putter"]
    for i, club in enumerate(clubs):
        t = await client.post(
            "/v1/analyses/upload-token",
            headers=auth_headers,
            json={
                "file_name": f"swing{i}.mp4",
                "file_size": 1024 * 1024,
                "file_type": "video/mp4",
                "duration": 4.0 + i,
            },
        )
        token = t.json()["data"]
        fake_minio.mark_uploaded(token["key"], size=1024 * 1024)
        await client.post(
            "/v1/analyses",
            headers=auth_headers,
            json={
                "upload_id": token["upload_id"],
                "camera_angle": "face_on",
                "club_type": club,
            },
        )

    # 全部
    r = await client.get("/v1/analyses?page=1&page_size=10", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["total"] >= 3
    ids = [it["club_type"] for it in body["items"]]
    assert set(clubs).issubset(set(ids))

    # 按 club_type 筛选
    r2 = await client.get("/v1/analyses?club_type=driver", headers=auth_headers)
    assert r2.status_code == 200
    body2 = r2.json()["data"]
    assert all(it["club_type"] == "driver" for it in body2["items"])
    assert body2["total"] >= 1

    # 分页 page_size=1
    r3 = await client.get("/v1/analyses?page=1&page_size=1", headers=auth_headers)
    body3 = r3.json()["data"]
    assert len(body3["items"]) == 1
    assert body3["has_more"] is True


@pytest.mark.asyncio
async def test_get_report_forbidden_for_other_user(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_minio: FakeMinioStorage,
):
    """A 创建的分析，B 不能访问（403）。"""
    t = await client.post(
        "/v1/analyses/upload-token",
        headers=auth_headers,
        json={
            "file_name": "swing.mp4",
            "file_size": 1024 * 1024,
            "file_type": "video/mp4",
            "duration": 5.0,
        },
    )
    token = t.json()["data"]
    fake_minio.mark_uploaded(token["key"], size=1024 * 1024)
    r = await client.post(
        "/v1/analyses",
        headers=auth_headers,
        json={
            "upload_id": token["upload_id"],
            "camera_angle": "face_on",
            "club_type": "driver",
        },
    )
    aid = r.json()["data"]["analysis_id"]

    # B 用户
    login_b = await client.post(
        "/v1/auth/wechat-login", json={"code": "pytest_stranger_xxxx"}
    )
    hb = {"Authorization": f"Bearer {login_b.json()['data']['token']}"}

    forbidden = await client.get(f"/v1/analyses/{aid}/status", headers=hb)
    assert forbidden.status_code == 403
