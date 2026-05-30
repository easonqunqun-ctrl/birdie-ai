"""W22 待办 #3 · (angle, category) 二维标尺合成单测。

覆盖 ``score_profiles.resolve_phase_weights`` / ``resolve_ideal`` 的合成规则：
- 相位权重：增量叠加 + 归一化；灰度安全（iron+无机位==V1）；两维复合。
- ideal：优先级 category > angle > V1。
"""

from __future__ import annotations

import pytest

from app.pipeline.angle_profiles import phase_weights_for
from app.pipeline.club_profiles import phase_weights_for_category
from app.pipeline.constants import PHASE_ORDER, PHASE_WEIGHTS
from app.pipeline.score_profiles import resolve_ideal, resolve_phase_weights

# ---------- resolve_phase_weights ----------


def test_phase_weights_none_none_equals_v1() -> None:
    """两维都 None → V1 单套。"""
    assert resolve_phase_weights(None, None) == pytest.approx(PHASE_WEIGHTS)


def test_phase_weights_iron_no_angle_equals_v1_gray_safe() -> None:
    """灰度安全：iron + 无机位 → V1（iron delta 0、angle delta 0）。"""
    assert resolve_phase_weights(None, "iron") == pytest.approx(PHASE_WEIGHTS)


def test_phase_weights_driver_no_angle_equals_category_only() -> None:
    """B-1 兼容：driver + 无机位 → 与纯 category 套一致。"""
    assert resolve_phase_weights(None, "driver") == pytest.approx(
        phase_weights_for_category("driver")
    )


def test_phase_weights_iron_face_on_equals_angle_only() -> None:
    """iron(delta 0) + face_on → 与纯 angle 套一致。"""
    assert resolve_phase_weights("face_on", "iron") == pytest.approx(
        phase_weights_for("face_on")
    )


def test_phase_weights_two_dims_compose_and_sum_to_one() -> None:
    """driver + dtl 两维 delta 复合；与任一单维都不同；和为 1、全非负。"""
    combined = resolve_phase_weights("down_the_line", "driver")
    assert sum(combined.values()) == pytest.approx(1.0)
    assert all(w >= 0 for w in combined.values())
    assert set(combined) == set(PHASE_ORDER)
    assert combined != pytest.approx(phase_weights_for_category("driver"))
    assert combined != pytest.approx(phase_weights_for("down_the_line"))
    # 手算校验 downswing：.25 + (.29-.25) + (.28-.25) = .32
    assert combined["downswing"] == pytest.approx(0.32)


# ---------- resolve_ideal ----------


def test_ideal_category_takes_priority_over_angle() -> None:
    """shoulder_rotation_top 仅 driver category override；DTL 不再抬高肩转 ideal。"""
    assert resolve_ideal("shoulder_rotation_top", "down_the_line", "driver") == (
        35.0,
        100.0,
    )


def test_ideal_falls_back_to_angle_when_category_silent() -> None:
    """top_wrist_position 仅 dtl override、driver 未 override → 取 angle。"""
    assert resolve_ideal("top_wrist_position", "down_the_line", "driver") == (0.15, 0.38)


def test_ideal_angle_only_when_no_category() -> None:
    assert resolve_ideal("top_wrist_position", "down_the_line", None) == (0.15, 0.38)


def test_ideal_category_only_when_no_angle() -> None:
    assert resolve_ideal("shoulder_rotation_top", None, "driver") == (35.0, 100.0)


def test_ideal_falls_back_to_v1_when_neither_overrides() -> None:
    """knee_flexion_setup 两维都没 override → V1 ideal。"""
    from app.pipeline.constants import FEATURES

    v1 = next(
        (f["ideal_min"], f["ideal_max"]) for f in FEATURES if f["name"] == "knee_flexion_setup"
    )
    assert resolve_ideal("knee_flexion_setup", "down_the_line", "driver") == v1


def test_ideal_unknown_feature_raises() -> None:
    with pytest.raises(KeyError):
        resolve_ideal("not_a_feature", "face_on", "driver")
