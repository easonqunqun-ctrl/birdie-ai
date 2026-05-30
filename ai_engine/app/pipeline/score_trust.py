"""可信度量与 overall 校准：拉开「可测好挥杆」与「低可信噪音片」的分差。"""

from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.feature_measurability import (
    MIN_MEASURABILITY_TO_SCORE,
    WARN_ANGLE_LIMITED_SCORING,
    measurability,
)
from app.pipeline.constants import FEATURES_BY_PHASE, PHASE_ORDER

WARN_SCORE_LOW_TRUST = "score_low_trust"

# 计分时低于此 confidence 的特征不参与（与 measurability 并列）
MIN_FEATURE_CONFIDENCE_TO_SCORE = 0.42

CORE_PHASES = ("downswing", "impact")
CORE_FEATURES = (
    "downswing_sequence",
    "wrist_release_timing",
    "wrist_release_angle",
    "spine_angle_impact_delta",
    "tempo_ratio",
)


@dataclass(frozen=True)
class TrustMetrics:
    core_confidence: float
    measurable_ratio: float
    scored_feature_count: int


def compute_trust_metrics(
    feature_confidences: dict[str, float] | None,
    *,
    camera_angle: str | None,
) -> TrustMetrics:
    if not feature_confidences:
        return TrustMetrics(
            core_confidence=0.75,
            measurable_ratio=1.0,
            scored_feature_count=15,
        )
    core_vals = [feature_confidences[n] for n in CORE_FEATURES if n in feature_confidences]
    core_conf = sum(core_vals) / len(core_vals) if core_vals else 0.5

    measurable = 0
    total = 0
    for phase in PHASE_ORDER:
        for meta in FEATURES_BY_PHASE.get(phase, []):
            name = meta["name"]
            if feature_confidences is not None and name not in feature_confidences:
                continue
            total += 1
            conf = feature_confidences.get(name, 0.0) if feature_confidences else 0.75
            if (
                measurability(name, camera_angle) >= MIN_MEASURABILITY_TO_SCORE
                and conf >= MIN_FEATURE_CONFIDENCE_TO_SCORE
            ):
                measurable += 1
    ratio = measurable / total if total else 1.0
    return TrustMetrics(
        core_confidence=core_conf,
        measurable_ratio=ratio,
        scored_feature_count=measurable,
    )


def calibrate_trusted_overall(
    overall: int,
    phase_scores: dict[str, int],
    *,
    feature_confidences: dict[str, float] | None,
    analysis_confidence: float,
    quality_warnings: list[str],
    camera_angle: str | None,
) -> tuple[int, list[str]]:
    """根据可测性 + 核心阶段表现校准 overall；返回 (新分, 额外 warnings)。"""
    extra: list[str] = []
    metrics = compute_trust_metrics(feature_confidences, camera_angle=camera_angle)

    impact = phase_scores.get("impact", 0)
    down = phase_scores.get("downswing", 0)
    core_phase_avg = (impact + down) / 2.0

    adjusted = float(overall)

    # 低可信 / 可测特征过少：整体降权（office 扫把、遮挡、转播噪音）
    low_trust = (
        analysis_confidence < 0.52
        or metrics.core_confidence < 0.50
        or metrics.measurable_ratio < 0.45
    )
    if low_trust:
        trust_mul = 0.72 + 0.28 * max(analysis_confidence, metrics.core_confidence)
        adjusted *= trust_mul
        adjusted = min(adjusted, 52.0)
        if WARN_SCORE_LOW_TRUST not in quality_warnings:
            extra.append(WARN_SCORE_LOW_TRUST)

    # 核心阶段测得稳 + 击球/下杆好：适度上浮（职业/规范练习片）
    elif (
        metrics.core_confidence >= 0.62
        and metrics.measurable_ratio >= 0.45
        and core_phase_avg >= 75.0
        and analysis_confidence >= 0.58
    ):
        boost = min(14.0, (core_phase_avg - 68.0) * 0.38)
        adjusted += boost

    # DTL 转播片：机位受限但下杆/击球强 → 避免被「中等可信」回归拉低
    elif (
        quality_warnings
        and WARN_ANGLE_LIMITED_SCORING in quality_warnings
        and core_phase_avg >= 82.0
        and overall >= 78
    ):
        adjusted = max(adjusted, min(92.0, overall + 4.0))

    # 中等可信：轻度回归中性，避免 everyone 挤在 50–60
    elif metrics.core_confidence < 0.58 or metrics.measurable_ratio < 0.50:
        if core_phase_avg >= 80.0:
            adjusted = max(adjusted, overall * 0.96)
        else:
            adjusted = adjusted * 0.88 + 50.0 * 0.12

    return int(round(max(0.0, min(100.0, adjusted)))), extra
