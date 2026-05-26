"""P2-M9-03 · AC-3 硬门槛：known_injuries **禁止透传至外部 LLM API**。

docs/06 §13.1：已知伤病字段为"高敏感"，仅用于本地训练建议生成。

测试策略
--------
1. 扫描 `chat_prompt.py` 源码 / 渲染输出，确保不含任何伤病关键字
2. 显式 build_chat_context（如果存在）→ 校验输出不含枚举值
3. 训练 plan 建议生成不依赖 LLM（仅本地 drill 算法）→ 独立路径，本测试不覆盖

若未来 LLM prompt 需引用伤病信息，需先评审 docs/06 §13.1 + 把字段加白名单 +
更新本测试为正向校验（"伤病以 hashed token 形式注入"等替代方案）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

# 伤病枚举键 + 中文标签（kickoff §3.3.3 + INJURY_OPTIONS）
INJURY_KEYS = (
    "lower_back",
    "shoulder",
    "elbow",
    "wrist",
    "knee",
    "hip",
    "neck",
)

INJURY_CN_LABELS = (
    "腰部",
    "肩部",
    "肘关节",
    "手腕",
    "膝盖",
    "髋关节",
    "颈部",
)

CHAT_PROMPT_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "chat_prompt.py"


def test_chat_prompt_source_does_not_reference_injury_keys():
    """静态守门：chat_prompt.py 源码不出现伤病关键字 / `known_injuries`。

    若日后产品确实要把伤病注入 LLM，需先评审 docs/06 §13.1 风险评估，
    并修改本测试为白名单注入校验（如 hashed token）。
    """
    assert CHAT_PROMPT_PATH.exists(), f"chat_prompt.py 不存在：{CHAT_PROMPT_PATH}"
    source = CHAT_PROMPT_PATH.read_text(encoding="utf-8")

    assert "known_injuries" not in source, (
        "chat_prompt.py 不应引用 known_injuries 字段；docs/06 §13.1 禁止"
    )

    for key in INJURY_KEYS:
        assert key not in source, (
            f"chat_prompt.py 含伤病枚举键 {key!r}；不允许透传 LLM"
        )

    for label in INJURY_CN_LABELS:
        assert label not in source, (
            f"chat_prompt.py 含伤病中文标签 {label!r}；不允许透传 LLM"
        )


def test_chat_service_source_does_not_reference_injury_keys():
    """同理校验 chat_service.py（防止绕过 chat_prompt 直接拼字符串）。"""
    chat_svc = (
        Path(__file__).resolve().parents[1] / "app" / "services" / "chat_service.py"
    )
    if not chat_svc.exists():
        pytest.skip("chat_service.py 不存在")
    source = chat_svc.read_text(encoding="utf-8")
    assert "known_injuries" not in source
    for key in INJURY_KEYS:
        assert key not in source


def test_user_presenter_does_not_leak_injuries():
    """build_user_response / user_presenter 不应回吐 known_injuries 字段。

    UserResponse schema 一期只含 level/goals/freq；二期 profile-v2 字段必须走
    独立的 `/v1/users/me/profile-v2` 端点（kickoff §4.1），避免被 chat 上下文消费。
    """
    presenter = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "user_presenter.py"
    )
    if not presenter.exists():
        pytest.skip("user_presenter.py 不存在")
    source = presenter.read_text(encoding="utf-8")
    assert "known_injuries" not in source
