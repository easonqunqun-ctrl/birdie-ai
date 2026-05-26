"""P2-M9-03 · onboarding 2.0 自动 consent 推断 helper。

依赖 M9-01 PR #90：`user_profile_v2_service.upsert_profile` + `PrivacyPayload` schema。

为什么独立模块
--------------
- M9-01 `upsert_profile` 要求调用方**同时**传字段值 + `privacy_payload`
- 新 onboarding UI 6 题流程中，用户填了 `handicap_self` 就应自动认为 consent
  打开（kickoff §4.2）；让客户端管理 consent 既冗余又易错
- 把"字段值 → consent 推断"独立成 helper：
  * 客户端只需传字段值；service 自动 fill consent
  * 维持 M9-01 service API 不变（向后兼容 M9-02 / M9-05 等场景）
"""

from __future__ import annotations

from app.schemas.user_profile_v2 import PrivacyPayload, UserProfileV2Update

# 字段 → consent 映射（与 user_profile_v2_service._CONSENT_TO_COLUMNS 反向）
FIELD_TO_CONSENT: dict[str, str] = {
    "handicap_official": "handicap_consent",
    "handicap_self": "handicap_consent",
    "handicap_source": "handicap_consent",
    "height_cm": "body_consent",
    "weight_kg": "body_consent",
    # handedness 不算"敏感"，不需 consent（与 docs/06 §13.1 一致）
    "known_injuries": "injury_consent",
    "favorite_course_ids": "location_consent",
    "coach_visible_fields": "coach_visible_consent",
}


def infer_consent_for_update(
    payload: UserProfileV2Update,
    existing_payload: PrivacyPayload | dict | None = None,
) -> PrivacyPayload:
    """根据 payload 中显式提供的字段自动推断/合并 consent。

    规则：
    1. 起始值：existing_payload（如有），否则全 False
    2. 客户端显式传了 `payload.privacy_payload` → 以客户端 explicit 为准（覆盖推断）
    3. 否则按字段值推断：
       - 字段值非 None / 非空列表 → consent = True
       - 字段值显式 None / 空列表 → consent = False（清空意图）
       - 字段未在 payload 中出现 → 保持 existing 值不变
    """
    if isinstance(existing_payload, PrivacyPayload):
        start = existing_payload.model_dump()
    elif isinstance(existing_payload, dict):
        start = dict(existing_payload)
    else:
        start = {}

    # explicit privacy_payload takes precedence
    if payload.privacy_payload is not None:
        start.update(payload.privacy_payload.model_dump())
        return PrivacyPayload(**{**PrivacyPayload().model_dump(), **start})

    explicit = payload.model_dump(exclude_unset=True)
    explicit.pop("privacy_payload", None)

    # 按字段值推断 consent
    for field_name, value in explicit.items():
        consent_key = FIELD_TO_CONSENT.get(field_name)
        if consent_key is None:
            continue
        # 非空值 → consent True；显式 None / 空列表 → consent False
        if value is None or (isinstance(value, list) and len(value) == 0):
            start[consent_key] = False
        else:
            start[consent_key] = True

    # 填充缺省值（PrivacyPayload schema 要求 5 字段都有 bool 值）
    default = PrivacyPayload().model_dump()
    merged = {**default, **start}
    return PrivacyPayload(**merged)


def merged_update_payload(
    payload: UserProfileV2Update,
    existing_payload: PrivacyPayload | dict | None = None,
) -> UserProfileV2Update:
    """返回新 UserProfileV2Update，privacy_payload 已被推断/合并。

    便于在路由层一行接入 M9-01 upsert_profile。
    """
    auto_consent = infer_consent_for_update(payload, existing_payload)
    # 用 model_copy update 字段；不破坏原 payload
    return payload.model_copy(update={"privacy_payload": auto_consent})


__all__ = [
    "FIELD_TO_CONSENT",
    "infer_consent_for_update",
    "merged_update_payload",
]
