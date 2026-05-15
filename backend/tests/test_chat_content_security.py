"""P1-C1：AI 教练发送消息接入微信 msg_sec_check 内容安全审核.

覆盖
----
1. 普通文本通过审核 → 200，扣减配额
2. 含敏感关键词的文本（mock 分支命中）→ 400 + 40017，**配额不被消耗**
3. 单元层面 `check_text` 在 mock 模式下对正常 / 违规文本的判定
4. 单元层面 `check_text` 在 fail-open 路径上的行为（HTTP 异常）

为什么"违规不消耗配额"很重要？
-----------------------------
旧实现里 `prepare_turn` 是 "扣配额 → 落 user_msg → 调 LLM"，把内容审核放在
最前面（任何扣减/落库之前）才能保证：
- 用户写错话、被审核拦截，不会平白无故掉一次今日额度
- user_message 不会落库（避免审核日志中残留违规原文）
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from httpx import AsyncClient

from app.integrations import wechat_security


# ==================== 1. API 集成：正常文本通过 ====================
@pytest.mark.asyncio
async def test_send_normal_message_passes_content_check(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    s = await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    sid = s.json()["data"]["session_id"]

    r = await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": "教练你好，我想知道我的握杆姿势怎么改进？"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"
    # 免费配额 5，扣 1 后剩 4
    assert body["quota_remaining"] == 4


# ==================== 2. API 集成：违规文本被拒，且不扣配额 ====================
@pytest.mark.asyncio
async def test_send_violation_message_rejected_without_quota_consumption(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """关键：违规文本必须返回 40017，且**配额不被扣减**。"""
    s = await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    sid = s.json()["data"]["session_id"]

    # 发一条正常消息扣到 4
    r0 = await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": "正常的一句话"},
        headers=auth_headers,
    )
    assert r0.status_code == 200
    assert r0.json()["data"]["quota_remaining"] == 4

    # 发违规消息（mock 关键词）
    r_bad = await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": "这是一段含违规字样的内容"},
        headers=auth_headers,
    )
    assert r_bad.status_code == 400, r_bad.text
    assert r_bad.json()["code"] == 40017

    # 再发一条正常消息：配额应仍是 4 → 3，证明上一条被拒时没消耗配额
    r1 = await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": "再来一句正常话"},
        headers=auth_headers,
    )
    assert r1.status_code == 200
    assert r1.json()["data"]["quota_remaining"] == 3


# ==================== 3. API 集成：违规文本不会落库为 user_message ====================
@pytest.mark.asyncio
async def test_violation_message_does_not_persist_user_message(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    s = await client.post("/v1/chat/sessions", json={}, headers=auth_headers)
    sid = s.json()["data"]["session_id"]

    # 发一条违规消息
    r_bad = await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": "violation 触发 mock 拦截"},
        headers=auth_headers,
    )
    assert r_bad.status_code == 400
    assert r_bad.json()["code"] == 40017

    # 历史里应当没有这条消息
    page = await client.get(
        f"/v1/chat/sessions/{sid}/messages?page=1&page_size=20",
        headers=auth_headers,
    )
    data = page.json()["data"]
    contents = [m["content"] for m in data["items"]]
    assert all("violation" not in c for c in contents)


# ==================== 4. 单元：check_text mock 分支（违规命中） ====================
@pytest.mark.asyncio
async def test_check_text_mock_violation() -> None:
    res = await wechat_security.check_text(
        "这是一段违规的描述",
        openid="o_test_openid",
    )
    assert res.passed is False
    assert res.suggest == "risky"
    assert res.reason


# ==================== 5. 单元：check_text mock 分支（正常通过） ====================
@pytest.mark.asyncio
async def test_check_text_mock_passes_normal_text() -> None:
    res = await wechat_security.check_text(
        "教练我握杆怎么调整？",
        openid="o_test_openid",
    )
    assert res.passed is True
    assert res.suggest == "pass"


# ==================== 6. 单元：空文本短路 ====================
@pytest.mark.asyncio
async def test_check_text_empty_short_circuits() -> None:
    res = await wechat_security.check_text("", openid="o_test_openid")
    assert res.passed is True


# ==================== 7. 单元：远程 HTTP 异常 → fail open ====================
@pytest.mark.asyncio
async def test_check_text_http_error_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """微信侧 HTTP 异常时，应 fail open（passed=True + reason），避免拖垮主链路。"""
    # 关掉 mock，强制走远程分支
    monkeypatch.setattr(wechat_security.settings, "WECHAT_MOCK_LOGIN", False)

    async def _fake_token(force_refresh: bool = False) -> str:
        return "fake_token"

    monkeypatch.setattr(wechat_security, "get_access_token", _fake_token)

    class _RaisingClient:
        async def __aenter__(self) -> _RaisingClient:
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

        async def post(self, *_a: object, **_k: object) -> httpx.Response:
            raise httpx.ConnectError("simulated network down")

    with patch.object(wechat_security.httpx, "AsyncClient", lambda timeout=10.0: _RaisingClient()):
        res = await wechat_security.check_text(
            "正常的一句话", openid="o_test_openid"
        )

    assert res.passed is True
    assert res.reason and "fail open" in res.reason
