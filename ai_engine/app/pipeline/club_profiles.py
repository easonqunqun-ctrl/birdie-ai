"""P2-M7-05 · 球杆差异化标尺：club_type → club_category 派生 + 5 套 PHASE_WEIGHTS。

详 docs/release-notes/p2-m7-05-club-profiles-kickoff.md v0.1。

设计要点
--------
- 一期 `client/src/types/api.ts ClubType` 共 11 值（含 unknown）
- 派生 6 类 `ClubCategory`：driver / wood / hybrid / iron / wedge / putter
- putter 走 P2-M7-11 独立 pipeline；本任务不为 putter 提供 PHASE_WEIGHTS
- 与 P2-M7-04 双 angle 标尺正交：scoring 层做 `(angle, category)` 二维选套
- 未知 club_type → fallback 'iron' + 生成 `unknown_club_type` engine_warning

与 M7-04 关系
-------------
- 本模块只暴露"category 维"单维表 + helper
- 二维 `(angle, category)` 笛卡尔积由 scoring.py 自行组合（W22 接入）
"""

from __future__ import annotations

from typing import Literal

from app.pipeline.constants import FEATURES, PHASE_ORDER, PHASE_WEIGHTS, FeatureMeta
from app.pipeline.engine_warnings import EngineWarning

ClubCategory = Literal["driver", "wood", "hybrid", "iron", "wedge", "putter"]

# ============================================================
# 22→6 派生映射（kickoff §3.2，与 client types/api.ts L10-13 1:1 对齐）
# ============================================================

# 一期实际 ClubType 11 值（含 unknown）；kickoff §3.2 提到的"22 值"是规划上限
# 含 wedge_pw/aw/sw/lw 与 hybrid 等扩展枚举。本表只对当前 11 值精确映射，
# 其他扩展值由 fallback 'iron' 兜底，client 加新枚举时按这里 1:1 扩展。
_CLUB_TYPE_TO_CATEGORY: dict[str, ClubCategory] = {
    "driver": "driver",
    "fairway_wood": "wood",
    "iron_3": "iron",
    "iron_4": "iron",
    "iron_5": "iron",
    "iron_6": "iron",
    "iron_7": "iron",
    "iron_8": "iron",
    "iron_9": "iron",
    "wedge": "wedge",
    "putter": "putter",
    # 兼容未来扩展（types/api.ts 加值时已含映射）：
    "wedge_pw": "wedge",
    "wedge_aw": "wedge",
    "wedge_sw": "wedge",
    "wedge_lw": "wedge",
    "hybrid": "hybrid",
    # unknown → 走 fallback 路径（不在表中，由 to_club_category 兜底）
}


def to_club_category(club_type: str | None) -> ClubCategory:
    """22 → 6 派生；未知 / None / 'unknown' → fallback 'iron'。

    fallback 不抛错（一期数据可能有遗留 'unknown' 值），调用方可同时调用
    `unknown_club_type_warning()` 决定是否记 engine_warning。
    """
    if not club_type:
        return "iron"
    return _CLUB_TYPE_TO_CATEGORY.get(club_type, "iron")


def is_known_club_type(club_type: str | None) -> bool:
    return bool(club_type and club_type in _CLUB_TYPE_TO_CATEGORY)


def unknown_club_type_warning(club_type: str | None) -> EngineWarning | None:
    """`unknown_club_type` engine_warning 生成（仅当 club_type 真不在表中）。"""
    if club_type and club_type not in _CLUB_TYPE_TO_CATEGORY:
        return EngineWarning(
            code="unknown_club_type",
            level="info",
            detail=f"club_type={club_type!r} not in mapping; fallback to category=iron",
        )
    return None


# ============================================================
# 5 套 PHASE_WEIGHTS_BY_CATEGORY v0.1（kickoff §4.1）
# putter 缺席（M7-11 推杆 pipeline 负责）
# ============================================================

# driver（W22 标定）：开球木球架高、上升击球，力量来自宽上杆 + 下杆速度/顺序；
# setup / impact 精度权重相对低于铁杆与挖起杆（球架高，触球容错更大）。
# 相对 iron 基线（.15/.20/.15/.25/.15/.10）在 setup/backswing/downswing/impact 4 个相位
# 差异 ≥0.03，满足 W19 DoD「driver vs iron ≥3 相位差异」。
# 数值为领域知识驱动的标定初值；真实 ECS 争议样本（ENG-04 触发条≥20）到位后二次校准。
# 详 docs/release-notes/w22-driver-phase-weights-calibration.md。
PHASE_WEIGHTS_DRIVER: dict[str, float] = {
    "setup": 0.11,
    "backswing": 0.23,
    "top": 0.15,
    "downswing": 0.29,
    "impact": 0.12,
    "follow_through": 0.10,
}

PHASE_WEIGHTS_WOOD: dict[str, float] = {
    "setup": 0.13,
    "backswing": 0.20,
    "top": 0.15,
    "downswing": 0.27,
    "impact": 0.14,
    "follow_through": 0.11,
}

PHASE_WEIGHTS_HYBRID: dict[str, float] = {
    "setup": 0.14,
    "backswing": 0.20,
    "top": 0.15,
    "downswing": 0.26,
    "impact": 0.15,
    "follow_through": 0.10,
}

# iron 套与一期 PHASE_WEIGHTS 完全相同（保证 V1 → V2 灰度 7 铁报告分数不跳变）
PHASE_WEIGHTS_IRON: dict[str, float] = dict(PHASE_WEIGHTS)

PHASE_WEIGHTS_WEDGE: dict[str, float] = {
    "setup": 0.18,
    "backswing": 0.18,
    "top": 0.14,
    "downswing": 0.22,
    "impact": 0.18,
    "follow_through": 0.10,
}

PHASE_WEIGHTS_BY_CATEGORY: dict[str, dict[str, float]] = {
    "driver": PHASE_WEIGHTS_DRIVER,
    "wood": PHASE_WEIGHTS_WOOD,
    "hybrid": PHASE_WEIGHTS_HYBRID,
    "iron": PHASE_WEIGHTS_IRON,
    "wedge": PHASE_WEIGHTS_WEDGE,
    # putter 缺席 → 路由到 M7-11 推杆 pipeline
}

# Sums-to-1 守门（与 constants.PHASE_WEIGHTS 一致；启动时即 assert，避免线上漂移）
for _cat, _weights in PHASE_WEIGHTS_BY_CATEGORY.items():
    _s = sum(_weights.values())
    assert abs(_s - 1.0) < 1e-9, f"PHASE_WEIGHTS_BY_CATEGORY[{_cat}] 和={_s}，应为 1.0"
    assert set(_weights.keys()) == set(PHASE_ORDER), (
        f"PHASE_WEIGHTS_BY_CATEGORY[{_cat}] keys != PHASE_ORDER"
    )


def phase_weights_for_category(category: ClubCategory | None) -> dict[str, float]:
    """按 category 取 PHASE_WEIGHTS；缺失（含 putter）→ V1 PHASE_WEIGHTS 兜底。"""
    if category is None or category not in PHASE_WEIGHTS_BY_CATEGORY:
        return dict(PHASE_WEIGHTS)
    return dict(PHASE_WEIGHTS_BY_CATEGORY[category])


# ============================================================
# FEATURES_IDEAL_OVERRIDE_BY_CATEGORY v0.1（kickoff §4.2 仅列差异项）
# ============================================================

# 仅"机位与杆型敏感"特征 override；其他特征沿用 constants.FEATURES.ideal_min/max
# 数值为 W19 编码初值；W22 ECS 标定后回流 docs/05 §8.4。
FEATURES_IDEAL_OVERRIDE_BY_CATEGORY: dict[str, dict[str, tuple[float, float]]] = {
    "driver": {
        "tempo_ratio": (2.5, 4.0),
        "spine_angle_setup": (22.0, 32.0),
        "shoulder_rotation_top": (35.0, 100.0),
        "spine_angle_impact_delta": (0.0, 22.0),
        "head_lateral_shift": (0.0, 0.10),
    },
    "wood": {
        "tempo_ratio": (2.3, 3.8),
        "spine_angle_setup": (23.0, 33.0),
        "shoulder_rotation_top": (32.0, 95.0),
        "spine_angle_impact_delta": (0.0, 20.0),
        "head_lateral_shift": (0.0, 0.09),
    },
    # iron 与 wedge 间插值，W21 ECS 标定后细化
    "hybrid": {
        "tempo_ratio": (2.2, 3.8),
        "spine_angle_setup": (24.0, 34.0),
        "shoulder_rotation_top": (30.0, 95.0),
    },
    # iron 为基线，未 override（沿用一期 FEATURES）
    "wedge": {
        "tempo_ratio": (1.8, 3.2),
        "spine_angle_setup": (28.0, 38.0),
        "shoulder_rotation_top": (25.0, 85.0),
        "spine_angle_impact_delta": (0.0, 15.0),
        "head_lateral_shift": (0.0, 0.06),
    },
}


def ideal_for_category(
    feature_name: str,
    category: ClubCategory | None,
) -> tuple[float, float]:
    """按 category 查特征 ideal；未 override → V1 ideal 兜底。

    Raises:
        KeyError：feature_name 不在 constants.FEATURES（防 typo）
    """
    feat = _feature_meta_by_name(feature_name)
    if category and category in FEATURES_IDEAL_OVERRIDE_BY_CATEGORY:
        override = FEATURES_IDEAL_OVERRIDE_BY_CATEGORY[category].get(feature_name)
        if override is not None:
            return override
    return (feat["ideal_min"], feat["ideal_max"])


def _feature_meta_by_name(feature_name: str) -> FeatureMeta:
    for f in FEATURES:
        if f["name"] == feature_name:
            return f
    raise KeyError(f"未知特征 {feature_name}；全集见 constants.FEATURES")


# 一致性 sanity：override 表里的 feature 必须都在 constants.FEATURES
_FEATURE_NAMES = {f["name"] for f in FEATURES}
for _cat, _override in FEATURES_IDEAL_OVERRIDE_BY_CATEGORY.items():
    for _fn in _override:
        assert _fn in _FEATURE_NAMES, (
            f"FEATURES_IDEAL_OVERRIDE_BY_CATEGORY[{_cat}] 引用了不存在的 feature {_fn}"
        )


# ============================================================
# 差异化 smoke 阈值（W19 DoD：driver vs iron vs wedge 至少 3 个 phase 差异 >= 0.03）
# ============================================================

CATEGORY_WEIGHT_MIN_DIFF = 0.03


def category_weight_diff_count(cat_a: ClubCategory, cat_b: ClubCategory) -> int:
    """统计两 category 之间 PHASE_WEIGHTS 差异 ≥ CATEGORY_WEIGHT_MIN_DIFF 的 phase 数。"""
    wa = phase_weights_for_category(cat_a)
    wb = phase_weights_for_category(cat_b)
    return sum(1 for phase in PHASE_ORDER if abs(wa.get(phase, 0) - wb.get(phase, 0)) >= CATEGORY_WEIGHT_MIN_DIFF)
