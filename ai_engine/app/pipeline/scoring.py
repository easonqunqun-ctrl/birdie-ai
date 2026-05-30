"""W6-T2：动作评分（docs/05 §2.6）。

三层函数：
- `score_feature(value, ideal_min, ideal_max, tolerance)` → int[0,100]
- `score_phase(features, phase)` → int[0,100]（阶段内加权；机位可测性重归一化）
- `score_overall(phase_scores)` → int[0,100]（阶段间加权，由 PHASE_WEIGHTS 决定）

P2 护城河（feature_measurability.py）
------------------------------------
- 机位下不可测的特征不参与该阶段计分（权重重归一化）。
- 阶段内无可测特征 → 中性 50 分（禁止误伤为 0）。
- 有可测特征时阶段分不低于 PHASE_SCORE_FLOOR。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.pipeline.constants import FEATURES_BY_PHASE, PHASE_ORDER, PHASE_WEIGHTS
from app.pipeline.feature_measurability import (
    MIN_MEASURABILITY_TO_SCORE,
    PHASE_NEUTRAL_SCORE,
    PHASE_SCORE_FLOOR,
    measurability,
    phase_has_scorable_features,
)
from app.pipeline.score_trust import MIN_FEATURE_CONFIDENCE_TO_SCORE

if TYPE_CHECKING:
    from app.pipeline.angle_profiles import CameraAngleEnum
    from app.pipeline.club_profiles import ClubCategory


def score_feature(
    value: float,
    ideal_min: float,
    ideal_max: float,
    tolerance: float = 0.5,
) -> int:
    """单特征评分 0-100。

    算法（与 docs/05 §2.6 完全一致）：
    - 值在理想区间 → 85-100（越接近中点越高）
    - 在容忍区间内（偏离 ≤ `tolerance × 区间宽`）→ 0-84 线性
    - 超出容忍区间 → 0

    Examples:
        >>> score_feature(30, 25, 35)        # 中点
        100
        >>> score_feature(25, 25, 35)        # 边界
        85
        >>> score_feature(40, 25, 35)        # 偏离区间宽的 50%
        42
        >>> score_feature(100, 25, 35)       # 超出容忍
        0
    """
    if ideal_max <= ideal_min:
        return 85  # 配置错误，给个中性分

    if ideal_min <= value <= ideal_max:
        center = (ideal_min + ideal_max) / 2
        range_half = (ideal_max - ideal_min) / 2
        deviation = abs(value - center) / range_half  # [0, 1]
        return int(round(100 - deviation * 15))

    width = ideal_max - ideal_min
    if value < ideal_min:
        deviation = (ideal_min - value) / width
    else:
        deviation = (value - ideal_max) / width

    # 容忍范围外 → 0
    if deviation > tolerance:
        return 0
    # 线性从 84 → 0
    return int(round(84 * (1 - deviation / tolerance)))


def score_phase(
    features: dict[str, float],
    phase: str,
    *,
    club_category: ClubCategory | None = None,
    camera_angle: CameraAngleEnum | None = None,
    feature_confidences: dict[str, float] | None = None,
) -> int:
    """阶段分 = 该阶段内各**可测且高置信**特征分加权之和（权重重归一化）。"""
    phase_feats = FEATURES_BY_PHASE.get(phase, [])
    if not phase_feats:
        return 0

    resolve = None
    if club_category is not None or camera_angle is not None:
        from app.pipeline.score_profiles import resolve_ideal

        resolve = resolve_ideal

    weighted_sum = 0.0
    weight_total = 0.0
    for meta in phase_feats:
        name = meta["name"]
        meas = measurability(name, camera_angle)
        if meas < MIN_MEASURABILITY_TO_SCORE:
            continue
        if feature_confidences is not None:
            fc = feature_confidences.get(name, 0.0)
            if fc < MIN_FEATURE_CONFIDENCE_TO_SCORE:
                continue
        if name not in features:
            continue
        if resolve is not None:
            ideal_min, ideal_max = resolve(name, camera_angle, club_category)
        else:
            ideal_min, ideal_max = meta["ideal_min"], meta["ideal_max"]
        s = score_feature(
            features[name],
            ideal_min,
            ideal_max,
            meta["tolerance"],
        )
        w = meta["weight"] * meas
        weighted_sum += s * w
        weight_total += w

    if weight_total <= 0:
        return PHASE_NEUTRAL_SCORE

    phase_score = int(round(weighted_sum / weight_total))
    if phase_score < PHASE_SCORE_FLOOR:
        phase_score = PHASE_SCORE_FLOOR
    return phase_score


def collect_skipped_features_for_scoring(
    features: dict[str, float],
    *,
    camera_angle: CameraAngleEnum | None,
) -> set[str]:
    """计分时会跳过的特征名（供 quality_warnings / issue 过滤）。"""
    skipped: set[str] = set()
    for phase in PHASE_ORDER:
        for meta in FEATURES_BY_PHASE.get(phase, []):
            name = meta["name"]
            if name not in features:
                continue
            if measurability(name, camera_angle) < MIN_MEASURABILITY_TO_SCORE:
                skipped.add(name)
    return skipped


def score_overall(
    phase_scores: dict[str, int],
    *,
    club_category: ClubCategory | None = None,
    camera_angle: CameraAngleEnum | None = None,
    features: dict[str, float] | None = None,
    feature_confidences: dict[str, float] | None = None,
) -> int:
    """综合分 = 各阶段分按相位权重加权。

    W22（``docs/release-notes/w22-driver-phase-weights-calibration.md`` 待办 #1/#3）：
    ``club_category`` / ``camera_angle`` 任一非空时按二维合成相位权重
    （``score_profiles.resolve_phase_weights``，增量叠加 category + angle 两维 delta）；
    两者均 ``None`` → V1 单套 ``PHASE_WEIGHTS`` 兜底。**iron + 无 angle == V1 单套**
    （灰度安全，kickoff R-02）；真实分析 angle 必填，故 V2 桶内即便 iron 也带机位 delta。

    P2 v0.3：机位下整阶段无可测特征时，该阶段权重不参与综合分（重归一化），
    避免 DTL 上杆中性 50 分拉低职业转播片。
    """
    if club_category is None and camera_angle is None:
        weights = dict(PHASE_WEIGHTS)
    else:
        # 延迟 import：score_profiles 依赖 constants，scoring 也依赖 constants；
        # 函数级 import 规避顶层耦合，且仅在传 profile 时才触发。
        from app.pipeline.score_profiles import resolve_phase_weights

        weights = resolve_phase_weights(camera_angle, club_category)

    if features is not None and camera_angle is not None:
        excluded = {
            p
            for p in PHASE_ORDER
            if not phase_has_scorable_features(
                features,
                p,
                camera_angle=camera_angle,
                feature_confidences=feature_confidences,
            )
        }
        if excluded and len(excluded) < len(PHASE_ORDER):
            active = {p: w for p, w in weights.items() if p not in excluded}
            weight_total = sum(active.values())
            if weight_total > 0:
                weights = {p: active[p] / weight_total for p in active}

    total = 0.0
    for p, w in weights.items():
        total += phase_scores.get(p, 0) * w
    return int(round(total))


def weakest_phase(phase_scores: dict[str, int]) -> str:
    """返回分数最低的阶段 key；并列时按 PHASE_ORDER 取靠前那个（稳定选择）。"""
    if not phase_scores:
        return PHASE_ORDER[0]
    min_score = min(phase_scores.values())
    for p in PHASE_ORDER:
        if phase_scores.get(p, 100) == min_score:
            return p
    return PHASE_ORDER[0]


def score_all_phases(
    features: dict[str, float],
    *,
    club_category: ClubCategory | None = None,
    camera_angle: CameraAngleEnum | None = None,
    feature_confidences: dict[str, float] | None = None,
) -> dict[str, int]:
    """一次性算 6 个阶段分。``club_category`` / ``camera_angle`` 透传给 ``score_phase``。"""
    return {
        p: score_phase(
            features,
            p,
            club_category=club_category,
            camera_angle=camera_angle,
            feature_confidences=feature_confidences,
        )
        for p in PHASE_ORDER
    }
