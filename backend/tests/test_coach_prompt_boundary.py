"""P-02：教练非高尔夫话题边界 — 模板与 FakeLLM 回归门槛（无外链 LLM）."""

from __future__ import annotations

import pytest

from app.integrations.llm import FakeLLMClient
from app.models.user import User
from app.services.chat_prompt import ROLE_AND_STYLE, build_system_prompt


def test_system_prompt_requires_golf_only_boundary() -> None:
    assert "高尔夫" in ROLE_AND_STYLE
    assert "无关" in ROLE_AND_STYLE or "拒绝" in ROLE_AND_STYLE


def test_build_system_prompt_includes_profile_block() -> None:
    u = User(
        id="usr_testcoach",
        invite_code="ABCDE1",
        nickname="测试用户",
        golf_level="beginner",
    )
    sp = build_system_prompt(u, [])
    assert "测试用户" in sp or "初学" in sp
    assert "最近挥杆分析" in sp or "分析摘要" in sp


@pytest.mark.asyncio
async def test_fake_llm_can_simulate_refusal_for_regression(
    use_fake_llm: FakeLLMClient,
) -> None:
    """集成路径：会话消息由 chat_service 组装；此处仅断言 FakeLLM 可固定「拒答」供后续扩展用例."""
    use_fake_llm.set_reply(
        "我是高尔夫教练，只能讨论挥杆与球场练习哦。你可以说说今天的击球问题吗？",
        chunk_size=40,
    )

    chunks: list[str] = []
    async for c in use_fake_llm.stream_chat(
        [
            {"role": "system", "content": ROLE_AND_STYLE},
            {"role": "user", "content": "用量子物理解释股票涨跌"},
        ]
    ):
        if c.type == "content":
            chunks.append(c.delta)
    body = "".join(chunks)
    assert "高尔夫" in body
