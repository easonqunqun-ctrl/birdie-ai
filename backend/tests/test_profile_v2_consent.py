"""P2-M9-03 · profile_v2_consent helper 单测。

覆盖 kickoff §4.2：字段值 → consent 自动推断 + explicit 覆盖优先级。
依赖 M9-01 PR #90 的 UserProfileV2Update / PrivacyPayload schemas。
"""

from __future__ import annotations

import pytest

from app.schemas.user_profile_v2 import PrivacyPayload, UserProfileV2Update
from app.services.profile_v2_consent import (
    FIELD_TO_CONSENT,
    infer_consent_for_update,
    merged_update_payload,
)


# ============================================================
# 1. 字段 → consent 推断
# ============================================================


def test_filling_handicap_sets_handicap_consent_true():
    payload = UserProfileV2Update(handicap_self=18.5)
    consent = infer_consent_for_update(payload)
    assert consent.handicap_consent is True
    # 未碰过其他 consent → 默认 False
    assert consent.body_consent is False
    assert consent.injury_consent is False


def test_filling_body_data_sets_body_consent_true():
    payload = UserProfileV2Update(height_cm=175, weight_kg=70)
    consent = infer_consent_for_update(payload)
    assert consent.body_consent is True


def test_filling_injuries_sets_injury_consent_true():
    payload = UserProfileV2Update(known_injuries=["lower_back"])
    consent = infer_consent_for_update(payload)
    assert consent.injury_consent is True


def test_filling_handedness_does_not_trigger_any_consent():
    """handedness 非敏感（docs/06 §13.1），不应触发 consent。"""
    payload = UserProfileV2Update(handedness="right")
    consent = infer_consent_for_update(payload)
    assert consent.handicap_consent is False
    assert consent.body_consent is False
    assert consent.injury_consent is False


# ============================================================
# 2. 显式 None / 空列表 → consent False（清空意图）
# ============================================================


def test_explicit_none_clears_handicap_consent():
    existing = PrivacyPayload(handicap_consent=True)
    payload = UserProfileV2Update(handicap_self=None)
    consent = infer_consent_for_update(payload, existing)
    assert consent.handicap_consent is False


def test_explicit_empty_list_clears_injury_consent():
    existing = PrivacyPayload(injury_consent=True)
    payload = UserProfileV2Update(known_injuries=[])
    consent = infer_consent_for_update(payload, existing)
    assert consent.injury_consent is False


# ============================================================
# 3. 未在 payload 出现的字段 → 保留原 consent
# ============================================================


def test_unmentioned_fields_preserve_existing_consent():
    existing = PrivacyPayload(handicap_consent=True, body_consent=True, injury_consent=True)
    # 只更新 handedness（不属于任何 consent）
    payload = UserProfileV2Update(handedness="left")
    consent = infer_consent_for_update(payload, existing)
    assert consent.handicap_consent is True
    assert consent.body_consent is True
    assert consent.injury_consent is True


# ============================================================
# 4. 显式 privacy_payload 覆盖自动推断（kickoff §4.2 规则 2）
# ============================================================


def test_explicit_privacy_payload_overrides_inference():
    """客户端显式传 privacy_payload → 以 explicit 为准。"""
    payload = UserProfileV2Update(
        handicap_self=18.5,  # 值会让自动推断 handicap_consent=True
        privacy_payload=PrivacyPayload(handicap_consent=False),  # 但 explicit 关闭
    )
    consent = infer_consent_for_update(payload)
    assert consent.handicap_consent is False  # explicit 胜出


# ============================================================
# 5. existing_payload 接受多种类型
# ============================================================


def test_existing_payload_accepts_dict():
    consent = infer_consent_for_update(
        UserProfileV2Update(handicap_self=18.5),
        existing_payload={"body_consent": True},
    )
    assert consent.body_consent is True  # 保留
    assert consent.handicap_consent is True  # 推断


def test_existing_payload_accepts_pydantic():
    consent = infer_consent_for_update(
        UserProfileV2Update(handicap_self=18.5),
        existing_payload=PrivacyPayload(body_consent=True),
    )
    assert consent.body_consent is True
    assert consent.handicap_consent is True


def test_existing_payload_none_starts_all_false():
    consent = infer_consent_for_update(UserProfileV2Update())
    for key in (
        "handicap_consent",
        "body_consent",
        "injury_consent",
        "location_consent",
        "coach_visible_consent",
    ):
        assert getattr(consent, key) is False


# ============================================================
# 6. merged_update_payload 返回新对象，不破坏原 payload
# ============================================================


def test_merged_update_payload_does_not_mutate_original():
    payload = UserProfileV2Update(handicap_self=18.5)
    assert payload.privacy_payload is None  # 原 payload 没 privacy
    merged = merged_update_payload(payload)
    assert merged.privacy_payload is not None
    assert merged.privacy_payload.handicap_consent is True
    # 原 payload 仍未变
    assert payload.privacy_payload is None


# ============================================================
# 7. FIELD_TO_CONSENT 映射完整性
# ============================================================


def test_field_to_consent_maps_all_consent_keys():
    """每个 consent 都至少有一个字段映射到它（反向校验）。"""
    consent_keys = set(FIELD_TO_CONSENT.values())
    assert "handicap_consent" in consent_keys
    assert "body_consent" in consent_keys
    assert "injury_consent" in consent_keys
    assert "location_consent" in consent_keys
    assert "coach_visible_consent" in consent_keys


def test_handedness_not_in_field_to_consent():
    """handedness 不应触发 consent（docs/06 §13.1）。"""
    assert "handedness" not in FIELD_TO_CONSENT
