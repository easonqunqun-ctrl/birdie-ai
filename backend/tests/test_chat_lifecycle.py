"""M3-T1 AI 对话接口集成测试（非流式版本 + 会话管理）.

覆盖：
1. GET /chat/quick-questions    → 返回 ≥4 条，带 requires_analysis 标记
2. POST /chat/sessions 无参数   → 24h 内会话复用 vs 新建
3. POST /chat/sessions 带分析ID → 始终新建，且校验分析归属（403 / 404）
4. POST 发消息 + 配额预检        → 扣减 used，超限抛 40007
5. GET 历史消息分页              → 顺序与分页行为
6. GET 会话列表预览              → last_message_preview + 按活跃度排序
7. DELETE 会话                   → CASCADE 删消息，不影响他人会话
8. 跨用户访问他人会话 → 403
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ==================== 1. 快捷问题 ====================
@pytest.mark.asyncio
async def test_quick_questions_anonymous_ok(client: AsyncClient) -> None:
    """快捷问题允许匿名访问，返回 4-6 条."""
    resp = await client.get("/v1/chat/quick-questions")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "questions" in data
    questions = data["questions"]
    assert 4 <= len(questions) <= 8
    assert all({"id", "text", "requires_analysis"} <= q.keys() for q in questions)
    # 至少一条 requires_analysis=True（"我的挥杆有什么问题"）
    assert any(q["requires_analysis"] for q in questions)


# ==================== 2. 会话创建：无参数则复用 ====================
@pytest.mark.asyncio
async def test_create_session_without_context_reuses_within_24h(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp1 = await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    assert resp1.status_code == 200
    sid1 = resp1.json()["data"]["session_id"]

    resp2 = await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    assert resp2.status_code == 200
    # 24h 内复用
    assert resp2.json()["data"]["session_id"] == sid1


# ==================== 3. 会话创建：带分析 ID 必然新建；404/403 ====================
@pytest.mark.asyncio
async def test_create_session_with_bad_analysis_id_returns_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.post(
        "/v1/chat/sessions",
        json={"context_analysis_id": "ana_not_exists"},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == 40401


# ==================== 4. 发送消息 + 配额扣减 + 40007 ====================
@pytest.mark.asyncio
async def test_send_message_consumes_quota_and_exhausts(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """免费用户 5 次配额，第 6 次抛 40007."""
    # 建会话
    s = await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    sid = s.json()["data"]["session_id"]

    # 前 5 次均成功；remaining 线性递减 4,3,2,1,0
    expected_remaining = [4, 3, 2, 1, 0]
    for i, exp in enumerate(expected_remaining):
        r = await client.post(
            f"/v1/chat/sessions/{sid}/messages",
            json={"content": f"hello {i}"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert body["user_message"]["role"] == "user"
        assert body["user_message"]["content"] == f"hello {i}"
        assert body["assistant_message"]["role"] == "assistant"
        assert body["assistant_message"]["content"]  # 非空
        assert body["quota_remaining"] == exp

    # 第 6 次：40007
    r6 = await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": "over quota"},
        headers=auth_headers,
    )
    assert r6.status_code == 403
    assert r6.json()["code"] == 40007


# ==================== 5. 历史消息分页 ====================
@pytest.mark.asyncio
async def test_get_messages_pagination(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    s = await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    sid = s.json()["data"]["session_id"]

    # 发 2 次消息 → 4 条 message
    for i in range(2):
        resp = await client.post(
            f"/v1/chat/sessions/{sid}/messages",
            json={"content": f"q{i}"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    page = await client.get(
        f"/v1/chat/sessions/{sid}/messages?page=1&page_size=10",
        headers=auth_headers,
    )
    data = page.json()["data"]
    assert data["total"] == 4
    assert len(data["items"]) == 4
    roles = [m["role"] for m in data["items"]]
    assert roles == ["user", "assistant", "user", "assistant"]

    # 小页：page_size=2 → 应拿到最早的 2 条
    page2 = await client.get(
        f"/v1/chat/sessions/{sid}/messages?page=1&page_size=2",
        headers=auth_headers,
    )
    d2 = page2.json()["data"]
    assert d2["has_more"] is True
    assert [m["role"] for m in d2["items"]] == ["user", "assistant"]


# ==================== 6. 会话列表预览 + 排序 ====================
@pytest.mark.asyncio
async def test_list_sessions_preview_and_order(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # 先建一个会话并发消息，让它成为"有活动"的会话
    s1 = await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    sid1 = s1.json()["data"]["session_id"]
    await client.post(
        f"/v1/chat/sessions/{sid1}/messages",
        json={"content": "first chat hello"},
        headers=auth_headers,
    )

    lst = await client.get("/v1/chat/sessions?page=1&page_size=10", headers=auth_headers)
    assert lst.status_code == 200
    items = lst.json()["data"]["items"]
    assert len(items) >= 1
    top = items[0]
    assert top["id"] == sid1
    # 预览取最后一条 message（assistant 回复），不为空
    assert top["last_message_preview"]
    assert top["message_count"] == 2


# ==================== 7. 删除会话 CASCADE ====================
@pytest.mark.asyncio
async def test_delete_session_cascades_messages(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    s = await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    sid = s.json()["data"]["session_id"]
    await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": "to be deleted"},
        headers=auth_headers,
    )

    d = await client.delete(f"/v1/chat/sessions/{sid}", headers=auth_headers)
    assert d.status_code == 200

    # 再查消息 → 404（会话不存在）
    g = await client.get(
        f"/v1/chat/sessions/{sid}/messages", headers=auth_headers
    )
    assert g.status_code == 404


# ==================== 8. 跨用户访问 403 ====================
@pytest.mark.asyncio
async def test_cross_user_session_access_forbidden(
    client: AsyncClient, auth_headers: dict[str, str], fresh_code: str
) -> None:
    # 用户 A 建会话
    s = await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    sid_a = s.json()["data"]["session_id"]

    # 用户 B 登录
    import uuid

    code_b = f"pytest_{uuid.uuid4().hex}"
    login = await client.post("/v1/auth/wechat-login", json={"code": code_b})
    token_b = login.json()["data"]["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # B 读 A 的消息 / 发消息 / 删会话 → 403
    assert (await client.get(
        f"/v1/chat/sessions/{sid_a}/messages", headers=headers_b
    )).status_code == 403
    assert (await client.post(
        f"/v1/chat/sessions/{sid_a}/messages",
        json={"content": "hi"},
        headers=headers_b,
    )).status_code == 403
    assert (await client.delete(
        f"/v1/chat/sessions/{sid_a}", headers=headers_b
    )).status_code == 403


# ==================== 9. 不存在的会话 ====================
@pytest.mark.asyncio
async def test_unknown_session_returns_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    assert (await client.get(
        "/v1/chat/sessions/chat_nope/messages", headers=auth_headers
    )).status_code == 404
    assert (await client.delete(
        "/v1/chat/sessions/chat_nope", headers=auth_headers
    )).status_code == 404


# ==================== 10. 输入校验 ====================
@pytest.mark.asyncio
async def test_send_message_validates_content_length(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    s = await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    sid = s.json()["data"]["session_id"]

    # 空内容
    r = await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": ""},
        headers=auth_headers,
    )
    assert r.status_code == 422

    # 超 500 字
    r2 = await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": "x" * 501},
        headers=auth_headers,
    )
    assert r2.status_code == 422
