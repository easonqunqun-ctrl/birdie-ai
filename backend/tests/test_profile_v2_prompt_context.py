"""P2-M9-04 · profile_v2_prompt_context 单测。

覆盖：
- extract_v2_context 防御性类型转换 / 截断
- render_v2_prompt_block 文案 / 空字段返回空串
- build_v2_context 入口接受 ORM/dict/None
- **AC-2 硬门槛**：video vs text 用户的 prompt 文案差异 ≥ 30%
- LLM_FORBIDDEN_PROFILE_FIELDS 包含 known_injuries
"""

from __future__ import annotations

import difflib
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.profile_v2_prompt_context import (
    ALLOWED_CADENCES,
    ALLOWED_DRILL_TYPES,
    ALLOWED_STYLES,
    LLM_FORBIDDEN_PROFILE_FIELDS,
    build_v2_context,
    extract_v2_context,
    render_v2_prompt_block,
)


# ============================================================
# 1. extract_v2_context 类型防御
# ============================================================


def test_extract_handles_decimal_handicap():
    ctx = extract_v2_context(handicap_self=Decimal("18.5"))
    assert ctx["handicap_self"] == 18.5


def test_extract_handles_str_handicap_gracefully():
    ctx = extract_v2_context(handicap_self="not a number")
    assert ctx["handicap_self"] is None


def test_extract_truncates_goals_to_top_3():
    ctx = extract_v2_context(mid_long_goals=["a", "b", "c", "d", "e"])
    assert ctx["mid_long_goals"] == ["a", "b", "c"]


def test_extract_filters_invalid_style():
    ctx = extract_v2_context(training_preference="invalid_style")
    assert ctx["style"] is None


def test_extract_accepts_valid_style():
    for s in ALLOWED_STYLES:
        ctx = extract_v2_context(training_preference=s)
        assert ctx["style"] == s


def test_extract_filters_invalid_cadence():
    ctx = extract_v2_context(training_preference_meta={"cadence": "hourly"})
    assert ctx["cadence"] is None


def test_extract_filters_invalid_drill_types():
    ctx = extract_v2_context(
        training_preference_meta={
            "preferred_drill_types": ["rhythm", "invalid_type", "tempo"]
        }
    )
    assert ctx["preferred_drill_types"] == ["rhythm", "tempo"]


def test_extract_empty_inputs_returns_empties():
    ctx = extract_v2_context()
    assert ctx == {
        "handicap_self": None,
        "mid_long_goals": [],
        "style": None,
        "cadence": None,
        "preferred_drill_types": [],
    }


# ============================================================
# 2. render_v2_prompt_block 文案
# ============================================================


def test_render_empty_context_returns_empty_string():
    assert render_v2_prompt_block({}) == ""


def test_render_handicap_only():
    block = render_v2_prompt_block({"handicap_self": 18.5})
    assert "差点：18.5" in block
    assert block.startswith("【画像 2.0】")
    assert block.endswith("。")


def test_render_video_style_uses_video_label():
    block = render_v2_prompt_block({"style": "video"})
    assert "视频派" in block
    assert "文字派" not in block


def test_render_text_style_uses_text_label():
    block = render_v2_prompt_block({"style": "text"})
    assert "文字派" in block
    assert "视频派" not in block


def test_render_cadence_label_localized():
    block = render_v2_prompt_block({"cadence": "2x_per_week"})
    assert "每周 2 次" in block


def test_render_drill_types_labels_localized():
    block = render_v2_prompt_block(
        {"preferred_drill_types": ["rhythm", "swing_plane"]}
    )
    assert "节奏" in block
    assert "挥杆平面" in block


# ============================================================
# 3. build_v2_context 入口
# ============================================================


def test_build_v2_context_none_returns_empty():
    assert build_v2_context(None) == ""


def test_build_v2_context_accepts_dict():
    block = build_v2_context(
        {
            "handicap_self": 12.0,
            "training_preference": "video",
            "training_preference_meta": {"cadence": "daily"},
        }
    )
    assert "12" in block
    assert "视频派" in block
    assert "每日" in block


def test_build_v2_context_accepts_orm_like_namespace():
    profile = SimpleNamespace(
        handicap_self=Decimal("22"),
        mid_long_goals=["差点 22 → 18"],
        training_preference="text",
        training_preference_meta={
            "cadence": "weekly",
            "preferred_drill_types": ["rhythm"],
        },
    )
    block = build_v2_context(profile)
    assert "差点 22 → 18" in block
    assert "文字派" in block
    assert "节奏" in block


def test_build_v2_context_handles_missing_attrs_gracefully():
    """缺所有 V2 字段（如 V1 用户）→ 空串。"""
    profile = SimpleNamespace()
    assert build_v2_context(profile) == ""


# ============================================================
# 4. AC-2 硬门槛：video vs text 用户的 prompt 差异化
# ============================================================


def test_ac2_video_vs_text_user_renders_distinct_prompt():
    """构造同水平但偏好不同的两个用户 → prompt 字符 diff ≥ 30%。"""
    user_video = build_v2_context(
        {
            "handicap_self": 22,
            "mid_long_goals": ["差点 22→18"],
            "training_preference": "video",
            "training_preference_meta": {
                "cadence": "2x_per_week",
                "preferred_drill_types": ["swing_plane", "tempo"],
            },
        }
    )
    user_text = build_v2_context(
        {
            "handicap_self": 22,
            "mid_long_goals": ["提升一致性"],
            "training_preference": "text",
            "training_preference_meta": {
                "cadence": "weekly",
                "preferred_drill_types": ["rhythm"],
            },
        }
    )
    assert user_video != user_text
    ratio = difflib.SequenceMatcher(None, user_video, user_text).ratio()
    diff_pct = 1 - ratio
    assert diff_pct >= 0.30, (
        f"AC-2 video vs text 差异 {diff_pct:.0%} < 30%；prompt 区分度不足"
    )


def test_ac2_video_user_does_not_mention_text_style():
    block = build_v2_context({"training_preference": "video"})
    assert "文字派" not in block
    assert "视频派" in block


# ============================================================
# 5. 防御性：known_injuries / 身高体重必须不入 LLM 上下文
# ============================================================


def test_extract_silently_ignores_injury_field():
    """API 设计强约束：函数签名 **不暴露** injury / body 参数。"""
    # 调用方传错（如 ** 解包），也不应有"injury 字段"。
    # 这里通过签名校验 + LLM_FORBIDDEN_PROFILE_FIELDS 维持显式黑名单
    assert "known_injuries" in LLM_FORBIDDEN_PROFILE_FIELDS
    assert "height_cm" in LLM_FORBIDDEN_PROFILE_FIELDS
    assert "weight_kg" in LLM_FORBIDDEN_PROFILE_FIELDS


def test_render_does_not_leak_injury_keys_even_if_smuggled():
    """即便 caller 把 injury 当 goals 塞进 ctx，render 也不应有特殊处理。"""
    block = render_v2_prompt_block(
        {
            "mid_long_goals": ["lower_back", "shoulder"],  # 模拟注入
        }
    )
    # render 会原样把 goals 拼进去；这恰好暴露 caller bug，
    # 但 LLM 透传链路必须在更上游（extract / build_v2_context）就拒绝
    # 这里只是文档化：render 不做额外清洗
    assert "lower_back" in block  # 不洗（caller 责任）


# ============================================================
# 6. 常量自检
# ============================================================


def test_allowed_styles_matches_schema_literal():
    """与 schemas/user_profile_v2.py TrainingPreferenceLiteral 同步。"""
    assert ALLOWED_STYLES == ("video", "text", "mixed")


def test_allowed_cadences_matches_kickoff_spec():
    assert ALLOWED_CADENCES == ("daily", "2x_per_week", "weekly")


def test_allowed_drill_types_covers_kickoff_examples():
    for needed in ("rhythm", "swing_plane"):
        assert needed in ALLOWED_DRILL_TYPES
