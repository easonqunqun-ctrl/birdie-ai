"""P2-M7-04 · 双套评分标尺：face_on / down_the_line 各自 PHASE_WEIGHTS + ideal。

详 docs/release-notes/p2-m7-04-camera-angle-calibration-kickoff.md §4.1 / §4.2。

设计要点
--------
- face_on 视角更容易看 setup / impact 的脊柱角与击球质量；权重略提
- dtl 视角更容易看上杆平面 / 顶点位置 / 下杆顺序；权重略提
- 数值为 W19 起跑前 v0.1 草案；W21 ECS 标定后回流 docs/05 §2.6

向后兼容
--------
- 未传 angle → 返回 constants.PHASE_WEIGHTS（V1 单套，保持一期行为）
- 未在双套表中出现的 phase → fallback 到 V1 权重

与 M7-05 关系
------------
- M7-04 仅做"机位"维度的双套；M7-05 在其后叠加 `club_category`，组合矩阵由 M7-05 实现
"""

from __future__ import annotations

from typing import Literal

from app.pipeline.constants import (
    FEATURES,
    FeatureMeta,
    PHASE_ORDER,
    PHASE_WEIGHTS,
)

CameraAngleEnum = Literal["face_on", "down_the_line"]

# ============================================================
# 双套 PHASE_WEIGHTS v0.1（kickoff §4.1）
# ============================================================

# face_on 突出 setup / impact / follow_through（正面看姿势变形）
PHASE_WEIGHTS_FACE_ON: dict[str, float] = {
    "setup": 0.18,
    "backswing": 0.18,
    "top": 0.13,
    "downswing": 0.22,
    "impact": 0.17,
    "follow_through": 0.12,
}
assert abs(sum(PHASE_WEIGHTS_FACE_ON.values()) - 1.0) < 1e-9, (
    "PHASE_WEIGHTS_FACE_ON 必须和为 1"
)

# down_the_line 突出 backswing / top / downswing（侧面看路径平面）
PHASE_WEIGHTS_DOWN_THE_LINE: dict[str, float] = {
    "setup": 0.12,
    "backswing": 0.22,
    "top": 0.18,
    "downswing": 0.28,
    "impact": 0.12,
    "follow_through": 0.08,
}
assert abs(sum(PHASE_WEIGHTS_DOWN_THE_LINE.values()) - 1.0) < 1e-9, (
    "PHASE_WEIGHTS_DOWN_THE_LINE 必须和为 1"
)

PHASE_WEIGHTS_BY_ANGLE: dict[str, dict[str, float]] = {
    "face_on": PHASE_WEIGHTS_FACE_ON,
    "down_the_line": PHASE_WEIGHTS_DOWN_THE_LINE,
}


def phase_weights_for(angle: CameraAngleEnum | None) -> dict[str, float]:
    """选 PHASE_WEIGHTS；None 或未知 → 一期单套兜底（向后兼容）。"""
    if angle is None or angle not in PHASE_WEIGHTS_BY_ANGLE:
        return dict(PHASE_WEIGHTS)
    return dict(PHASE_WEIGHTS_BY_ANGLE[angle])


# ============================================================
# 双套 ideal 范围 v0.1（kickoff §4.2 至少 3 特征）
# ============================================================

# Override 仅对"机位差异敏感"的特征生效；未列出的特征沿用 V1 ideal_min/max。
# 字段含义同 FeatureMeta；W21 ECS 标定后扩到全 15 特征。
IDEAL_OVERRIDES_BY_ANGLE: dict[str, dict[str, tuple[float, float]]] = {
    "face_on": {
        # 正面看脊柱前倾更准
        "spine_angle_setup": (24.0, 36.0),
        # 击球脊柱前倾偏离更敏感（正面易看）
        "spine_angle_impact_delta": (0.0, 15.0),
        # 头部水平位移在 face_on 比 dtl 显得更大（透视效应）
        "head_lateral_shift": (0.0, 0.10),
    },
    "down_the_line": {
        # dtl 看顶点手腕位置更稳定 → 收紧 ideal
        "top_wrist_position": (0.15, 0.38),
        # dtl 是看肩平面的最佳视角，肩旋转角度可看到全幅
        "shoulder_rotation_top": (60.0, 100.0),
        # dtl 看左臂伸直度比 face_on 准
        "left_arm_straightness": (170.0, 180.0),
    },
}


def ideal_for_angle(
    feature_name: str,
    angle: CameraAngleEnum | None,
) -> tuple[float, float]:
    """按机位查特征 ideal 范围。

    - 命中 IDEAL_OVERRIDES_BY_ANGLE[angle][feature] → 返回 override
    - 否则 → 返回 FEATURES 表中的 V1 ideal（向后兼容 + 缺数据兜底）

    Raises:
        KeyError：feature_name 不在 constants.FEATURES（防 typo）
    """
    feat = _feature_meta_by_name(feature_name)
    if angle and angle in IDEAL_OVERRIDES_BY_ANGLE:
        override = IDEAL_OVERRIDES_BY_ANGLE[angle].get(feature_name)
        if override is not None:
            return override
    return (feat["ideal_min"], feat["ideal_max"])


def _feature_meta_by_name(feature_name: str) -> FeatureMeta:
    for f in FEATURES:
        if f["name"] == feature_name:
            return f
    raise KeyError(f"未知特征 {feature_name}；全集见 constants.FEATURES")


# ============================================================
# 双套差异化 smoke 校验（kickoff W19 DoD）
# 单测断言两个 PHASE_WEIGHTS 至少在 backswing 或 downswing 上差异 >= 0.03
# ============================================================

PHASE_WEIGHT_MIN_DIFF = 0.03


def phase_weights_diff(angle_a: CameraAngleEnum, angle_b: CameraAngleEnum) -> dict[str, float]:
    """逐 phase 计算 |w_a - w_b|，供单测断言双套确实有差异化。"""
    wa = phase_weights_for(angle_a)
    wb = phase_weights_for(angle_b)
    return {phase: abs(wa.get(phase, 0) - wb.get(phase, 0)) for phase in PHASE_ORDER}
