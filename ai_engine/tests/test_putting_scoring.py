"""P2-M7-11 W24 · 推杆评分单测。"""

from __future__ import annotations


from app.pipeline.putting.constants import (
    PUTTING_FEATURE_WEIGHTS,
    putting_feature_meta,
)
from app.pipeline.putting.scoring import (
    score_putting,
    score_putting_feature,
    score_putting_overall,
)


def test_lower_is_better_zero_value_is_perfect() -> None:
    """稳定度特征 value=0（完美稳定）→ 100。"""
    meta = putting_feature_meta("pendulum_stability")
    assert score_putting_feature(0.0, meta) == 100


def test_lower_is_better_at_ideal_max_is_85() -> None:
    meta = putting_feature_meta("head_stability")
    assert score_putting_feature(meta["ideal_max"], meta) == 85


def test_lower_is_better_far_beyond_is_zero() -> None:
    meta = putting_feature_meta("face_alignment")
    # 远超 ideal_max + tolerance×width → 0
    far = meta["ideal_max"] + (meta["ideal_max"] - meta["ideal_min"]) * (meta["tolerance"] + 1)
    assert score_putting_feature(far, meta) == 0


def test_lower_is_better_monotonic_decreasing() -> None:
    meta = putting_feature_meta("pendulum_stability")
    lo = score_putting_feature(meta["ideal_max"] * 0.25, meta)
    hi = score_putting_feature(meta["ideal_max"] * 0.75, meta)
    assert lo > hi


def test_tempo_ratio_in_band_scores_high() -> None:
    """tempo_ratio 双边区间 [2.0,2.5]，中点 2.25 → 满分。"""
    meta = putting_feature_meta("tempo_ratio")
    assert score_putting_feature(2.25, meta) == 100
    assert score_putting_feature(1.0, meta) < 85  # 偏离区间


def test_score_putting_overall_weighting() -> None:
    """全特征满分 → overall=100；全 0 分 → 0。"""
    perfect = dict.fromkeys(PUTTING_FEATURE_WEIGHTS, 100)
    assert score_putting_overall(perfect) == 100
    assert score_putting_overall(dict.fromkeys(PUTTING_FEATURE_WEIGHTS, 0)) == 0


def test_score_putting_end_to_end_ideal() -> None:
    """理想推击（稳定度≈0、杆面方正、tempo=2.25）→ overall 高分。"""
    features = {
        "pendulum_stability": 0.0,
        "head_stability": 0.0,
        "face_alignment": 0.0,
        "tempo_ratio": 2.25,
    }
    out = score_putting(features)
    assert set(out) == {"overall", "features", "phases"}
    assert out["overall"] == 100
    assert set(out["phases"]) == {"setup", "backstroke", "impact", "follow"}
    assert all(0 <= v <= 100 for v in out["phases"].values())


def test_score_putting_missing_feature_is_zero() -> None:
    out = score_putting({"pendulum_stability": 0.0})  # 缺 3 个
    assert out["features"]["face_alignment"] == 0
    assert out["features"]["tempo_ratio"] == 0


def test_phases_reflect_bad_impact() -> None:
    """杆面差（face_alignment 大）→ impact 阶段分明显低于 setup。"""
    features = {
        "pendulum_stability": 0.0,
        "head_stability": 0.0,
        "face_alignment": 90.0,  # 极差
        "tempo_ratio": 2.25,
    }
    phases = score_putting(features)["phases"]
    assert phases["impact"] < phases["setup"]
    assert phases["impact"] == 0


def test_overall_is_int_0_100() -> None:
    out = score_putting(
        {
            "pendulum_stability": 0.0002,
            "head_stability": 0.0005,
            "face_alignment": 3.0,
            "tempo_ratio": 2.1,
        }
    )
    assert isinstance(out["overall"], int)
    assert 0 <= out["overall"] <= 100
