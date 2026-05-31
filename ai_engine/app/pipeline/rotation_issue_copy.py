"""P2-M7-R1 · A6 旋转类 issue 文案：sanity 失败时用固定句，不展示荒谬度数。

与 ``feature_measurability`` / ``rotation_track`` sanity 阈值对齐。
V1 ``diagnose.py`` 与 V2 ``_build_issue_from_rule_result`` 共用。

契约映射
--------
- ``quality_warnings`` code ``rotation_reading_unreliable``（``WARN_ROTATION_SANITY``）
  ↔ 客户端 ``QUALITY_WARNING_COPY.rotation_reading_unreliable``
  ↔ locale ``issues.rotation_unreliable.summary``（语义对齐，非 issue 卡片）
- 矛盾旋转 issue 合并时 ``finalize_diagnose_issues`` 追加同上 warning code（D4）
"""

from __future__ import annotations

from typing import Mapping

from app.pipeline.rule_engine import render_i18n_key

ROTATION_ISSUE_TYPES = frozenset(
    {"over_rotation", "under_rotation", "flat_shoulder", "steep_shoulder"}
)

# quality_warnings machine code（与 ``feature_measurability.WARN_ROTATION_SANITY`` 同值）
ROTATION_READING_UNRELIABLE_CODE = "rotation_reading_unreliable"

DISPLAY_SHOULDER_MIN = 15.0
DISPLAY_SHOULDER_MAX = 110.0
DISPLAY_XFACTOR_MAX = 80.0

_cached_zh_cn: dict[str, str] | None = None


def get_zh_cn_locale() -> dict[str, str]:
    """懒加载 zh_CN locale（V1 diagnose 与单测共用）。"""
    global _cached_zh_cn
    if _cached_zh_cn is None:
        from app.pipeline.rule_engine import LOCALES_DIR, load_locale

        _cached_zh_cn = load_locale(LOCALES_DIR / "zh_CN.json")
    return _cached_zh_cn


def should_use_safe_rotation_summary(
    issue_type: str, metrics: Mapping[str, float]
) -> bool:
    """读数不在可展示 band 内 → 不用 ``{shoulder_rotation_top:.0f}°`` 插值模板。"""
    if issue_type in ("over_rotation", "under_rotation"):
        shoulder = metrics.get("shoulder_rotation_top")
        if shoulder is None:
            return True
        return shoulder < DISPLAY_SHOULDER_MIN or shoulder > DISPLAY_SHOULDER_MAX
    if issue_type in ("flat_shoulder", "steep_shoulder"):
        xf = metrics.get("x_factor")
        if xf is None:
            return True
        return xf <= 0.0 or xf > DISPLAY_XFACTOR_MAX
    return False


def render_rotation_issue_description(
    issue_type: str,
    metrics: Mapping[str, float],
    locale_dict: Mapping[str, str],
) -> str:
    """按 A6 契约返回 issue description（含 summary / summary_safe 分支）。"""
    if issue_type not in ROTATION_ISSUE_TYPES:
        summary_key = f"issues.{issue_type}.summary"
        return render_i18n_key(summary_key, metrics, locale_dict=locale_dict)

    if should_use_safe_rotation_summary(issue_type, metrics):
        safe_key = f"issues.{issue_type}.summary_safe"
        if safe_key in locale_dict:
            return locale_dict[safe_key]
        return locale_dict.get(
            "issues.rotation_unreliable.summary",
            "画面机位或遮挡导致 AI 无法稳定读取转肩角度，已跳过相关读数展示。",
        )

    summary_key = f"issues.{issue_type}.summary"
    return render_i18n_key(summary_key, metrics, locale_dict=locale_dict)
