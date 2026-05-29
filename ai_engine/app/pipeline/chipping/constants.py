"""P2-M7-12 · 切杆 mode 常量（特征 meta + 阶段/特征权重）。

详 ``docs/release-notes/p2-m7-12-chipping-pipeline-kickoff.md`` §3。上游真源 docs/23 §3.12。

与 putting / full_swing 的关系
-----------------------------
- **完全独立**：切杆 3 专属特征 + 4 阶段（setup/backswing/impact/follow）。
- 共享 MediaPipe pose 归一化坐标 [0,1]。

ideal 为 v0.1 占位，待 ECS chipping ≥10 段标定（AC-2 r≥0.65）。
"""

from __future__ import annotations

from typing import TypedDict

CHIPPING_PHASE_ORDER: list[str] = ["setup", "backswing", "impact", "follow"]

CHIPPING_PHASE_LABELS: dict[str, str] = {
    "setup": "瞄准准备",
    "backswing": "上杆",
    "impact": "击球",
    "follow": "收杆",
}


class ChippingFeatureMeta(TypedDict):
    name: str
    display_name: str
    phase: str
    unit: str
    ideal_min: float
    ideal_max: float
    tolerance: float
    weight: float
    lower_is_better: bool
    # contact_point_quality 已是 0-100 分，越高越好
    direct_score: bool


CHIPPING_FEATURES: list[ChippingFeatureMeta] = [
    {
        "name": "half_swing_amplitude",
        "display_name": "半挥幅度",
        "phase": "backswing",
        "unit": "ratio",  # 顶点上腕-耳距离 / 准备位肩-腕距离（相对全挥 proxy）
        "ideal_min": 0.3,
        "ideal_max": 0.6,
        "tolerance": 0.5,
        "weight": 0.35,
        "lower_is_better": False,
        "direct_score": False,
    },
    {
        "name": "face_open_angle",
        "display_name": "杆面开角",
        "phase": "impact",
        "unit": "deg",  # 切杆理想轻微开杆面 5-15°
        "ideal_min": 5.0,
        "ideal_max": 15.0,
        "tolerance": 0.5,
        "weight": 0.35,
        "lower_is_better": False,
        "direct_score": False,
    },
    {
        "name": "contact_point_quality",
        "display_name": "触球质量",
        "phase": "impact",
        "unit": "score",  # 0-100，手-脚-球位 proxy 三角几何
        "ideal_min": 75.0,
        "ideal_max": 100.0,
        "tolerance": 0.5,
        "weight": 0.30,
        "lower_is_better": False,
        "direct_score": True,
    },
]

CHIPPING_PHASE_WEIGHTS: dict[str, float] = {
    "setup": 0.15,
    "backswing": 0.30,
    "impact": 0.35,
    "follow": 0.20,
}

CHIPPING_FEATURE_WEIGHTS: dict[str, float] = {
    f["name"]: f["weight"] for f in CHIPPING_FEATURES
}

CHIPPING_PHASE_FEATURE_MAP: dict[str, list[str]] = {
    "setup": ["half_swing_amplitude"],
    "backswing": ["half_swing_amplitude"],
    "impact": ["face_open_angle", "contact_point_quality"],
    "follow": ["contact_point_quality"],
}


def chipping_feature_meta(name: str) -> ChippingFeatureMeta:
    for f in CHIPPING_FEATURES:
        if f["name"] == name:
            return f
    raise KeyError(f"未知切杆特征 {name}")


assert set(CHIPPING_PHASE_FEATURE_MAP) == set(CHIPPING_PHASE_ORDER)
_pw = sum(CHIPPING_PHASE_WEIGHTS.values())
assert abs(_pw - 1.0) < 1e-9
_fw = sum(CHIPPING_FEATURE_WEIGHTS.values())
assert abs(_fw - 1.0) < 1e-9
