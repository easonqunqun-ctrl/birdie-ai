"""W22 待办 #3 · (angle, category) 二维标尺合成。

把 M7-04 机位维（``angle_profiles``）与 M7-05 球杆维（``club_profiles``）合成单一
标尺，供 ``scoring`` 在 V2 灰度（``club_aware_scoring=True``）下使用。kickoff 一直把
「(angle, category) 笛卡尔积由 scoring 组合」列为 W22 接入项，这里落地组合规则。

合成规则（详 ``docs/release-notes/w22-driver-phase-weights-calibration.md`` §6 待办 #3）
------------------------------------------------------------------------------
- **相位权重**：增量叠加（用户决策 A）。base = V1 ``PHASE_WEIGHTS``；
  ``combined = V1 + (category套 − V1) + (angle套 − V1)``，clip 到 ≥0 后归一化。
  两维 delta 各自和为 0，故无 clip 时 combined 天然和为 1。
  - ``iron + 无 angle`` → V1（灰度安全，与 B-1 一致）；
  - ``driver + dtl`` → driver 与 dtl 两维 delta 复合；
  - **注意**：真实分析 angle 必填，故 V2 下即便 iron 也会带机位 delta，
    分数不再严格 == V1（这是 M7-04 机位标尺的本意，且仅 V2 灰度桶生效）。
- **per-feature ideal**：优先级 **category > angle > V1**（用户决策）。
  球杆类别决定「该动作的真实理想区间」，机位更多是测量视角的次要修正；
  同一特征被两维同时 override 时取 category。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.pipeline.angle_profiles import IDEAL_OVERRIDES_BY_ANGLE, phase_weights_for
from app.pipeline.club_profiles import (
    FEATURES_IDEAL_OVERRIDE_BY_CATEGORY,
    ideal_for_category,
    phase_weights_for_category,
)
from app.pipeline.constants import PHASE_ORDER, PHASE_WEIGHTS

if TYPE_CHECKING:
    from app.pipeline.angle_profiles import CameraAngleEnum
    from app.pipeline.club_profiles import ClubCategory


def resolve_phase_weights(
    camera_angle: CameraAngleEnum | None,
    club_category: ClubCategory | None,
) -> dict[str, float]:
    """二维相位权重 = V1 + (category − V1) + (angle − V1)，clip≥0 后归一化。"""
    cat_w = phase_weights_for_category(club_category)
    ang_w = phase_weights_for(camera_angle)
    raw: dict[str, float] = {}
    for p in PHASE_ORDER:
        base = PHASE_WEIGHTS[p]
        combined = base + (cat_w[p] - base) + (ang_w[p] - base)
        raw[p] = combined if combined > 0 else 0.0
    total = sum(raw.values())
    if total <= 0:  # 理论不可达（两维 delta 和为 0）；兜底防 0 除
        return dict(PHASE_WEIGHTS)
    return {p: raw[p] / total for p in PHASE_ORDER}


def resolve_ideal(
    feature_name: str,
    camera_angle: CameraAngleEnum | None,
    club_category: ClubCategory | None,
) -> tuple[float, float]:
    """per-feature ideal：category override > angle override > V1。

    Raises:
        KeyError：feature_name 不在 constants.FEATURES（由兜底分支的
        ``ideal_for_category`` 校验，防 typo）。
    """
    if club_category and club_category in FEATURES_IDEAL_OVERRIDE_BY_CATEGORY:
        ov = FEATURES_IDEAL_OVERRIDE_BY_CATEGORY[club_category].get(feature_name)
        if ov is not None:
            return ov
    if camera_angle and camera_angle in IDEAL_OVERRIDES_BY_ANGLE:
        ov = IDEAL_OVERRIDES_BY_ANGLE[camera_angle].get(feature_name)
        if ov is not None:
            return ov
    # 兜底 V1 ideal（category=None → ideal_for_category 返回 constants.FEATURES 区间，
    # 同时校验 feature_name 合法）
    return ideal_for_category(feature_name, None)
