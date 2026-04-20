"""M3-T2 AI 对话流式接入（LLM + system prompt + SSE + 速率限制）集成测试.

覆盖：
1. SSE 事件序列正确：message_start → content_delta × N → attachment × 0..K → message_end
2. message_end 落库后 completion_tokens > 0（FakeLLM 会填充 usage）
3. drill_card heuristic 命中：回复文本含"髋部旋转" → attachment.type=drill_card
4. LLM 错误（FakeLLM set_mode("error")）→ error 事件 + 配额退回
5. LLM 流中超时（FakeLLM set_mode("timeout")）→ error 事件 + 配额退回（有部分文本）
6. 速率限制 40009：21 次/分钟触发
7. system prompt 注入：最近 3 次分析的 overall_score / issue 被塞进 messages[0].content
8. JSON 降级路径：LLM 失败时抛 50106
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.integrations.llm import FakeLLMClient
from app.models.analysis import AnalysisIssue, SwingAnalysis
from app.models.chat import ChatMessage, ChatQuota


# ==================== 辅助 ====================
async def _create_session(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.post("/v1/chat/sessions", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["session_id"]


async def _collect_sse(
    client: AsyncClient, sid: str, content: str, headers: dict[str, str]
) -> list[tuple[str, dict]]:
    """发一次 SSE 请求，把所有事件解析成 (event_name, data_dict) 列表."""
    async with client.stream(
        "POST",
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": content},
        headers={**headers, "Accept": "text/event-stream"},
    ) as resp:
        assert resp.status_code == 200, await resp.aread()
        events: list[tuple[str, dict]] = []
        event_name = ""
        async for line in resp.aiter_lines():
            if line.startswith("event: "):
                event_name = line[len("event: ") :].strip()
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
                events.append((event_name, data))
            elif line == "":
                event_name = ""
        return events


async def _get_user_id_from_token(client: AsyncClient, headers: dict[str, str]) -> str:
    """通过 /users/me 接口拿当前用户 id（测试里只用来建造分析数据）."""
    resp = await client.get("/v1/users/me", headers=headers)
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


# ==================== 1. SSE 事件序列 ====================
@pytest.mark.asyncio
async def test_sse_event_sequence_ok(
    client: AsyncClient, auth_headers: dict[str, str], use_fake_llm: FakeLLMClient
) -> None:
    use_fake_llm.set_reply("这是一个关于挥杆技术的回复。")
    sid = await _create_session(client, auth_headers)

    events = await _collect_sse(client, sid, "你好", auth_headers)
    event_names = [e[0] for e in events]

    # 第一条必须是 message_start，最后一条必须是 message_end
    assert event_names[0] == "message_start"
    assert event_names[-1] == "message_end"
    # 中间至少 1 条 content_delta
    assert event_names.count("content_delta") >= 1

    start_data = events[0][1]
    assert start_data["user_message"]["content"] == "你好"
    assert start_data["assistant_message_id"].startswith("msg_")

    end_data = events[-1][1]
    assert end_data["assistant_message_id"] == start_data["assistant_message_id"]
    assert end_data["content"] == "这是一个关于挥杆技术的回复。"
    assert end_data["quota_remaining"] == 4  # 消耗 1 次


# ==================== 2. completion_tokens 落库 ====================
@pytest.mark.asyncio
async def test_assistant_message_persists_usage(
    client: AsyncClient, auth_headers: dict[str, str], use_fake_llm: FakeLLMClient
) -> None:
    use_fake_llm.set_reply("短回复。")
    sid = await _create_session(client, auth_headers)
    events = await _collect_sse(client, sid, "问题", auth_headers)
    end = next(d for n, d in events if n == "message_end")
    assistant_msg_id = end["assistant_message_id"]

    async with AsyncSessionLocal() as db:
        msg = await db.get(ChatMessage, assistant_msg_id)
        assert msg is not None
        assert msg.content == "短回复。"
        assert (msg.completion_tokens or 0) > 0
        assert (msg.prompt_tokens or 0) > 0


# ==================== 3. drill_card heuristic ====================
@pytest.mark.asyncio
async def test_drill_card_attachment_detected(
    client: AsyncClient, auth_headers: dict[str, str], use_fake_llm: FakeLLMClient
) -> None:
    use_fake_llm.set_reply(
        "建议加强髋部旋转练习，每天 3 组。另外可以试试毛巾夹臂练习。"
    )
    sid = await _create_session(client, auth_headers)
    events = await _collect_sse(client, sid, "怎么练", auth_headers)

    attachments = [d["attachment"] for n, d in events if n == "attachment"]
    drill_ids = [a["drill_id"] for a in attachments]
    assert "drill_hip_rotation" in drill_ids
    assert "drill_towel_arm" in drill_ids

    end = next(d for n, d in events if n == "message_end")
    assert len(end["attachments"]) == 2


# ==================== 4. LLM error → error 事件 + 配额退回 ====================
@pytest.mark.asyncio
async def test_llm_error_refunds_quota_and_emits_error(
    client: AsyncClient, auth_headers: dict[str, str], use_fake_llm: FakeLLMClient
) -> None:
    use_fake_llm.set_mode("error", error_message="连接 LLM 失败")
    sid = await _create_session(client, auth_headers)

    events = await _collect_sse(client, sid, "你好", auth_headers)
    event_names = [e[0] for e in events]
    assert "error" in event_names
    assert "message_end" not in event_names
    err = next(d for n, d in events if n == "error")
    assert err["code"] == 50106

    # 配额已退回：当前用户 used 应为 0
    user_id = await _get_user_id_from_token(client, auth_headers)
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(
                select(ChatQuota).where(ChatQuota.user_id == user_id)
            )
        ).scalars().first()
        assert row is not None
        assert row.used == 0


# ==================== 5. timeout 中段失败 ====================
@pytest.mark.asyncio
async def test_llm_timeout_mid_stream_preserves_partial(
    client: AsyncClient, auth_headers: dict[str, str], use_fake_llm: FakeLLMClient
) -> None:
    use_fake_llm.set_mode("timeout")  # 吐一段 + error
    sid = await _create_session(client, auth_headers)

    events = await _collect_sse(client, sid, "你好", auth_headers)
    event_names = [e[0] for e in events]
    assert event_names[0] == "message_start"
    assert event_names.count("content_delta") >= 1
    assert "error" in event_names

    # 部分文本已落库（含"[回复中断..."）
    async with AsyncSessionLocal() as db:
        msgs = (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == sid)
                .order_by(ChatMessage.created_at.asc())
            )
        ).scalars().all()
        # user + partial assistant = 2 条
        assert len(msgs) == 2
        assert msgs[1].role == "assistant"
        assert "回复中断" in msgs[1].content


# ==================== 6. 速率限制 40009 ====================
@pytest.mark.asyncio
async def test_rate_limit_40009(
    client: AsyncClient,
    auth_headers: dict[str, str],
    use_fake_llm: FakeLLMClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_fake_llm.set_reply("ok")
    # 把配额拉到足够大，避免 40007 先被触发
    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(ChatQuota))).scalars().first()
        if row is not None:
            row.total = 9999
            await db.commit()

    # 把速率上限改小到 3（window_sec 仍 60），避免测试里真的发 21 次
    from app.core import rate_limit as rl_mod

    monkeypatch.setattr(rl_mod, "CHAT_SEND_LIMIT", 3)

    sid = await _create_session(client, auth_headers)

    # 前 3 次 OK；第 4 次 40009
    for _ in range(3):
        r = await client.post(
            f"/v1/chat/sessions/{sid}/messages",
            json={"content": "x"},
            headers=auth_headers,
        )
        assert r.status_code == 200

    r4 = await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": "x"},
        headers=auth_headers,
    )
    assert r4.status_code == 429
    assert r4.json()["code"] == 40009


# ==================== 7. system prompt 注入最近分析 ====================
@pytest.mark.asyncio
async def test_system_prompt_contains_recent_analyses(
    client: AsyncClient, auth_headers: dict[str, str], use_fake_llm: FakeLLMClient
) -> None:
    use_fake_llm.set_reply("好的。")
    user_id = await _get_user_id_from_token(client, auth_headers)

    # 直接写一条完成态分析进 DB
    async with AsyncSessionLocal() as db:
        analysis = SwingAnalysis(
            id=new_id("ana"),
            user_id=user_id,
            video_url="http://test/v.mp4",
            camera_angle="face_on",
            club_type="iron_7",
            status="completed",
            overall_score=72,
            analyzed_at=datetime.now(UTC),
        )
        db.add(analysis)
        await db.flush()
        issue = AnalysisIssue(
            id=new_id("iss"),
            analysis_id=analysis.id,
            issue_type="casting",
            name="抛杆",
            severity="high",
            description="手腕过早释放",
        )
        db.add(issue)
        await db.commit()

    sid = await _create_session(client, auth_headers)
    await _collect_sse(client, sid, "帮我看看", auth_headers)

    # FakeLLM 记录了最近一次 messages
    last_call = use_fake_llm.calls[-1]
    sys_prompt = last_call["messages"][0]["content"]
    assert last_call["messages"][0]["role"] == "system"
    # 注入成功：能看到分数 72 和问题"抛杆"
    assert "72" in sys_prompt
    assert "抛杆" in sys_prompt
    # 角色设定也在
    assert "小鸟 AI 高尔夫教练" in sys_prompt


# ==================== 8. JSON 降级路径失败抛 50106 ====================
@pytest.mark.asyncio
async def test_json_fallback_raises_50106_on_llm_error(
    client: AsyncClient, auth_headers: dict[str, str], use_fake_llm: FakeLLMClient
) -> None:
    use_fake_llm.set_mode("error")
    sid = await _create_session(client, auth_headers)

    r = await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": "你好"},
        headers={**auth_headers, "Accept": "application/json"},
    )
    assert r.status_code == 502
    assert r.json()["code"] == 50106


# ==================== 9. JSON 降级路径正常流程 ====================
@pytest.mark.asyncio
async def test_json_fallback_ok(
    client: AsyncClient, auth_headers: dict[str, str], use_fake_llm: FakeLLMClient
) -> None:
    use_fake_llm.set_reply("这是一个测试回复。")
    sid = await _create_session(client, auth_headers)

    r = await client.post(
        f"/v1/chat/sessions/{sid}/messages",
        json={"content": "你好"},
        headers={**auth_headers, "Accept": "application/json"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["assistant_message"]["content"] == "这是一个测试回复。"
    assert data["quota_remaining"] == 4


# ==================== 10. slow 模式事件节奏 ====================
@pytest.mark.asyncio
async def test_slow_mode_yields_multiple_deltas(
    client: AsyncClient, auth_headers: dict[str, str], use_fake_llm: FakeLLMClient
) -> None:
    use_fake_llm.set_mode("slow", delay_per_chunk=0.01)
    use_fake_llm.set_reply("a" * 80, chunk_size=8)  # 期望 10 个 chunk
    sid = await _create_session(client, auth_headers)

    started = asyncio.get_event_loop().time()
    events = await _collect_sse(client, sid, "你好", auth_headers)
    elapsed = asyncio.get_event_loop().time() - started

    content_deltas = [e for e in events if e[0] == "content_delta"]
    assert len(content_deltas) >= 5
    # slow 模式 0.01s × 10 = 0.1s，加 overhead 至少 >0.05s
    assert elapsed > 0.05
