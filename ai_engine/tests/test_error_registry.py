"""P2-M7-03 · 错误码 registry 完整性单测。

详 docs/release-notes/p2-m7-03-error-codes-kickoff.md §6.1。

CI 门禁：本测试保证 ERROR_REGISTRY 覆盖 50101-50105 + 50106-50123 全 23 个码，
且每个码都有非空中文 user_message + 严重度合法。
"""

from __future__ import annotations

import pytest

from app.errors import (
    ERROR_REGISTRY,
    PipelineError,
    all_registered_codes,
    get_error_class,
)

# 一期保留段
LEGACY_CODES: tuple[int, ...] = (50101, 50102, 50103, 50104, 50105)

# P2-M7-03 扩展段
V2_CODES: tuple[int, ...] = tuple(range(50106, 50124))

# 合计 23 码（≥ docs/23 AC-1 要求的 20）
EXPECTED_CODES: tuple[int, ...] = LEGACY_CODES + V2_CODES


# ============================================================
# 1. registry 完整性
# ============================================================


def test_registry_covers_all_legacy_codes():
    for code in LEGACY_CODES:
        assert code in ERROR_REGISTRY, f"legacy 码 {code} 未注册"


def test_registry_covers_all_v2_codes():
    for code in V2_CODES:
        assert code in ERROR_REGISTRY, f"v2 码 {code} 未注册"


def test_registry_total_count_meets_ac1():
    assert len(ERROR_REGISTRY) == len(EXPECTED_CODES)
    assert len(ERROR_REGISTRY) >= 20, "AC-1 要求 ≥ 20 个错误码"


def test_all_registered_codes_sorted():
    codes = all_registered_codes()
    assert codes == sorted(codes)
    assert codes[0] == 50101
    assert codes[-1] == 50123


# ============================================================
# 2. 每个码必须有非空文案 + 正确 code 字段
# ============================================================


@pytest.mark.parametrize("code", EXPECTED_CODES)
def test_each_code_has_non_empty_user_message(code: int):
    cls = ERROR_REGISTRY[code]
    instance = cls("test detail")
    assert instance.user_message, f"码 {code} ({cls.__name__}) user_message 为空"
    assert instance.code == code, f"码 {code} 的 cls.code 不一致"


@pytest.mark.parametrize("code", EXPECTED_CODES)
def test_each_code_user_message_is_chinese(code: int):
    cls = ERROR_REGISTRY[code]
    instance = cls("")
    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in instance.user_message)
    assert has_chinese, f"码 {code} ({cls.__name__}) user_message 缺中文"


@pytest.mark.parametrize("code", EXPECTED_CODES)
def test_each_code_user_message_length_limit(code: int):
    cls = ERROR_REGISTRY[code]
    instance = cls("")
    assert len(instance.user_message) <= 80, (
        f"码 {code} ({cls.__name__}) user_message 超 80 字（NFR）"
    )


# ============================================================
# 3. get_error_class 查询行为
# ============================================================


def test_get_error_class_returns_registered():
    assert get_error_class(50106).__name__ == "VideoTooShortError"
    assert get_error_class(50120).__name__ == "DecodeError"


def test_get_error_class_returns_base_on_unknown():
    assert get_error_class(50999) is PipelineError
    assert get_error_class(0) is PipelineError


# ============================================================
# 4. 关键码语义抽样验证
# ============================================================


def test_50106_video_too_short_message():
    inst = ERROR_REGISTRY[50106]("")
    assert "3 秒" in inst.user_message


def test_50109_low_light_message():
    inst = ERROR_REGISTRY[50109]("")
    assert "光线" in inst.user_message


def test_50110_camera_shake_message():
    inst = ERROR_REGISTRY[50110]("")
    assert "三脚架" in inst.user_message or "手持" in inst.user_message


def test_50113_partial_body_message():
    inst = ERROR_REGISTRY[50113]("")
    assert "完整" in inst.user_message or "退后" in inst.user_message


def test_50120_decode_error_message():
    inst = ERROR_REGISTRY[50120]("")
    assert "H.264" in inst.user_message or "格式" in inst.user_message


# ============================================================
# 5. 50122 / 50123 占位码（业务逻辑在 M7-07 / M10）
# ============================================================


def test_50122_multi_swing_placeholder():
    cls = ERROR_REGISTRY[50122]
    assert cls.__name__ == "MultiSwingOverflowError"
    inst = cls("")
    assert "挥杆" in inst.user_message


def test_50123_mode_club_mismatch_placeholder():
    cls = ERROR_REGISTRY[50123]
    assert cls.__name__ == "ModeClubMismatchError"
    inst = cls("")
    assert "推杆" in inst.user_message or "球杆" in inst.user_message


# ============================================================
# 6. registry 不能漏空隙
# ============================================================


def test_no_gap_in_v2_range():
    """50106-50123 段不允许漏号；docs/23 §11.4 段位连续约定。"""
    for code in range(50106, 50124):
        assert code in ERROR_REGISTRY, f"v2 段漏号: {code}"
