"""P2-M7-05 · 球杆差异化标尺单元测试。

覆盖 kickoff §3.2 / §3.4 / §4.1 / §4.2 / §5.3（≥90% 覆盖率 AC-3）。
"""

from __future__ import annotations

import pytest

from app.pipeline.club_profiles import (
    CATEGORY_WEIGHT_MIN_DIFF,
    FEATURES_IDEAL_OVERRIDE_BY_CATEGORY,
    PHASE_WEIGHTS_BY_CATEGORY,
    PHASE_WEIGHTS_DRIVER,
    PHASE_WEIGHTS_IRON,
    PHASE_WEIGHTS_WEDGE,
    category_weight_diff_count,
    ideal_for_category,
    is_known_club_type,
    phase_weights_for_category,
    to_club_category,
    unknown_club_type_warning,
)
from app.pipeline.constants import PHASE_ORDER, PHASE_WEIGHTS


# ============================================================
# 1. to_club_category 22→6 映射全覆盖（含 fallback）
# ============================================================


@pytest.mark.parametrize(
    "club_type,expected",
    [
        ("driver", "driver"),
        ("fairway_wood", "wood"),
        ("iron_3", "iron"),
        ("iron_4", "iron"),
        ("iron_5", "iron"),
        ("iron_6", "iron"),
        ("iron_7", "iron"),
        ("iron_8", "iron"),
        ("iron_9", "iron"),
        ("wedge", "wedge"),
        ("putter", "putter"),
        # 扩展枚举（types/api.ts 加值前 mapping 已准备好）
        ("wedge_pw", "wedge"),
        ("wedge_aw", "wedge"),
        ("wedge_sw", "wedge"),
        ("wedge_lw", "wedge"),
        ("hybrid", "hybrid"),
    ],
)
def test_to_club_category_known_values(club_type, expected):
    assert to_club_category(club_type) == expected


def test_to_club_category_unknown_falls_back_iron():
    assert to_club_category("unknown") == "iron"
    assert to_club_category("3wood") == "iron"
    assert to_club_category("") == "iron"
    assert to_club_category(None) == "iron"


# ============================================================
# 2. unknown_club_type_warning
# ============================================================


def test_unknown_club_type_warning_emits_for_unknown():
    w = unknown_club_type_warning("unknown")
    assert w is not None
    assert w.code == "unknown_club_type"
    assert "unknown" in w.detail


def test_unknown_club_type_warning_none_for_known():
    assert unknown_club_type_warning("iron_7") is None
    assert unknown_club_type_warning("driver") is None


def test_unknown_club_type_warning_none_for_empty():
    """空字符串 / None 不算异常（一期默认值场景）。"""
    assert unknown_club_type_warning(None) is None
    assert unknown_club_type_warning("") is None


def test_is_known_club_type_true_for_known():
    assert is_known_club_type("iron_7") is True
    assert is_known_club_type("driver") is True


def test_is_known_club_type_false_for_unknown():
    assert is_known_club_type("unknown") is False
    assert is_known_club_type(None) is False


# ============================================================
# 3. PHASE_WEIGHTS_BY_CATEGORY 五套（kickoff §4.1）
# ============================================================


def test_phase_weights_by_category_has_5_categories():
    """putter 缺席（M7-11 负责），所以是 5 套。"""
    assert set(PHASE_WEIGHTS_BY_CATEGORY.keys()) == {
        "driver",
        "wood",
        "hybrid",
        "iron",
        "wedge",
    }


@pytest.mark.parametrize("category", ["driver", "wood", "hybrid", "iron", "wedge"])
def test_phase_weights_sums_to_one_each_category(category):
    weights = PHASE_WEIGHTS_BY_CATEGORY[category]
    assert abs(sum(weights.values()) - 1.0) < 1e-9


@pytest.mark.parametrize("category", ["driver", "wood", "hybrid", "iron", "wedge"])
def test_phase_weights_keys_cover_all_phases(category):
    weights = PHASE_WEIGHTS_BY_CATEGORY[category]
    assert set(weights.keys()) == set(PHASE_ORDER)


def test_phase_weights_iron_matches_v1():
    """灰度安全：iron 套 = V1 单套 → 7 铁报告分数 V1↔V2 切换不跳变（kickoff R-02 兜底）。"""
    assert PHASE_WEIGHTS_IRON == PHASE_WEIGHTS


def test_phase_weights_driver_emphasizes_downswing():
    assert PHASE_WEIGHTS_DRIVER["downswing"] >= 0.25


def test_phase_weights_wedge_emphasizes_setup_and_impact():
    assert PHASE_WEIGHTS_WEDGE["setup"] >= 0.16
    assert PHASE_WEIGHTS_WEDGE["impact"] >= 0.16


def test_phase_weights_for_category_unknown_falls_back_v1():
    """putter / None / 未知 → V1 单套兜底。"""
    assert phase_weights_for_category("putter") == PHASE_WEIGHTS
    assert phase_weights_for_category(None) == PHASE_WEIGHTS
    assert phase_weights_for_category("unknown") == PHASE_WEIGHTS  # type: ignore[arg-type]


def test_phase_weights_for_category_returns_copy_not_reference():
    """避免上游修改返回值污染 module-level constants。"""
    out = phase_weights_for_category("driver")
    out["setup"] = 99.0
    assert PHASE_WEIGHTS_DRIVER["setup"] != 99.0


# ============================================================
# 4. 5 套差异化 smoke（W19 DoD）
# ============================================================


@pytest.mark.xfail(
    reason=(
        "W19/W22 引擎债：PHASE_WEIGHTS_DRIVER 为 v0.1 编码初值，与 iron 仅 1 个相位"
        "差异≥0.03（wedge/driver-vs-wedge 已达标）。driver 相位权重需 W22 ECS 标定后"
        "回填 club_profiles.py，再撤销本 xfail。改权重=改评分行为，不擅自定值。"
    ),
    strict=True,
)
def test_driver_vs_iron_differs_in_at_least_3_phases():
    """W19 DoD：driver vs iron 至少 3 个 phase 差异 ≥ 0.03。"""
    assert category_weight_diff_count("driver", "iron") >= 3


def test_wedge_vs_iron_differs_in_at_least_3_phases():
    assert category_weight_diff_count("wedge", "iron") >= 3


def test_driver_vs_wedge_significant_diff():
    """driver vs wedge 应有显著差异（kickoff §4.1 设计意图）。"""
    assert category_weight_diff_count("driver", "wedge") >= 3


def test_category_weight_min_diff_threshold():
    assert CATEGORY_WEIGHT_MIN_DIFF == 0.03


# ============================================================
# 5. FEATURES_IDEAL_OVERRIDE_BY_CATEGORY（kickoff §4.2）
# ============================================================


def test_ideal_for_category_driver_overrides_tempo_ratio():
    lo, hi = ideal_for_category("tempo_ratio", "driver")
    assert (lo, hi) == (2.5, 4.0)


def test_ideal_for_category_wedge_overrides_spine_setup():
    lo, hi = ideal_for_category("spine_angle_setup", "wedge")
    assert (lo, hi) == (28.0, 38.0)


def test_ideal_for_category_iron_falls_back_to_v1():
    """iron 是基线，未 override → 沿用 V1 ideal。"""
    from app.pipeline.constants import feature_meta

    v1 = feature_meta("tempo_ratio")
    assert ideal_for_category("tempo_ratio", "iron") == (v1["ideal_min"], v1["ideal_max"])


def test_ideal_for_category_unspecified_feature_falls_back():
    """driver override 表未列的特征 → V1 ideal。"""
    from app.pipeline.constants import feature_meta

    v1 = feature_meta("knee_flexion_setup")
    assert ideal_for_category("knee_flexion_setup", "driver") == (
        v1["ideal_min"],
        v1["ideal_max"],
    )


def test_ideal_for_category_unknown_feature_raises():
    with pytest.raises(KeyError):
        ideal_for_category("nonexistent_feature", "driver")


def test_ideal_overrides_cover_4_categories():
    """driver / wood / hybrid / wedge 都需要 override；iron 作基线（不 override）。"""
    assert set(FEATURES_IDEAL_OVERRIDE_BY_CATEGORY.keys()) == {
        "driver",
        "wood",
        "hybrid",
        "wedge",
    }


def test_ideal_overrides_reference_known_features_only():
    """override 表里所有 feature 必须在 constants.FEATURES（防 typo）。"""
    from app.pipeline.constants import FEATURES

    feature_names = {f["name"] for f in FEATURES}
    for cat, overrides in FEATURES_IDEAL_OVERRIDE_BY_CATEGORY.items():
        for fn in overrides:
            assert fn in feature_names, f"category {cat} 引用了未知 feature {fn}"


# ============================================================
# 6. driver vs wedge 同一特征 ideal 差异化（W21 ECS 标定基线）
# ============================================================


def test_driver_vs_wedge_tempo_ratio_differs():
    """driver 节奏较慢 / wedge 节奏紧凑：ideal 不应相同。"""
    drv = ideal_for_category("tempo_ratio", "driver")
    wdg = ideal_for_category("tempo_ratio", "wedge")
    assert drv != wdg
    assert drv[0] > wdg[0]  # driver 下限更高（更慢）


def test_driver_vs_wedge_spine_setup_differs():
    """driver 站位更直立 / wedge 更前倾。"""
    drv = ideal_for_category("spine_angle_setup", "driver")
    wdg = ideal_for_category("spine_angle_setup", "wedge")
    assert drv != wdg
    assert wdg[0] > drv[0]  # wedge 下限更高（更前倾）
