"""W6-T2：特征抽取单测。"""

from __future__ import annotations

import math

from app.pipeline.constants import FEATURES
from app.pipeline.features import extract_features
from app.pipeline.phases import segment_phases


def test_all_15_features_returned(synthetic_pose_result) -> None:
    """`extract_features` 必须返回恰好 15 个键（跟 constants.FEATURES 对齐），
    每个值都是有限 float。"""
    phases = segment_phases(synthetic_pose_result)
    feats = extract_features(synthetic_pose_result.keypoints, phases)

    expected = {f["name"] for f in FEATURES}
    assert set(feats.keys()) == expected
    for name, value in feats.items():
        assert isinstance(value, float), f"{name} 不是 float：{type(value)}"
        assert math.isfinite(value), f"{name} 非有限值：{value}"


def test_features_roughly_in_range_for_ideal_swing(synthetic_pose_result) -> None:
    """理想合成挥杆的关键特征应落在 ideal_min/max 附近（或至少在容忍 3 倍范围内）。

    这里不追求严格的数值符合（合成是粗糙的 2D 棒人模型，不可能跟真人完全一致），
    但至少"脊柱前倾角""膝弯角""左臂伸直度"这些单帧几何量应该接近 ideal 区间。
    """
    phases = segment_phases(synthetic_pose_result)
    feats = extract_features(synthetic_pose_result.keypoints, phases)

    # spine_angle_setup：合成是 face-on 视角、肩/髋中点同 x，理论脊柱角接近 0°。
    # 真实 down-the-line 视角才会出现前倾角；这里只要求在合理区间即可（不作为诊断关键）。
    assert 0.0 <= feats["spine_angle_setup"] <= 45.0

    # knee_flexion_setup：髋 (0.47, 0.58)-膝 (0.47, 0.73)-踝 (0.47, 0.90)，三点共线 → 180°
    assert feats["knee_flexion_setup"] > 160.0

    # left_arm_straightness @ top：shoulder(0.48,0.45)-elbow(0.42,0.25)-wrist(0.40,0.10)
    # 几乎成直线，夹角接近 180°
    assert feats["left_arm_straightness"] > 150.0

    # top_wrist_position @ top：lead=left wrist(0.40, 0.10)；nose(0.50, 0.25)
    # (nose.y - wrist.y) / 0.5 = 0.15 / 0.5 = 0.30 → 在 [0.1, 0.4] ideal
    assert 0.1 <= feats["top_wrist_position"] <= 0.5

    # head_lateral_shift：合成里 nose.x 始终 0.50，无位移
    assert feats["head_lateral_shift"] < 0.02

    # tempo_ratio：backswing = top - swing_start；downswing = impact - top
    # 约 (45-10)/(65-45) = 1.75；在 2.5-3.5 区间外，但 > 0 合理
    assert feats["tempo_ratio"] > 0.5


def test_extract_features_is_fault_tolerant() -> None:
    """奇异输入不崩溃；算不出的特征跳过（不再灌 ideal 中点虚高分）。"""
    import numpy as np

    from app.pipeline.phases import PhaseInfo, PhaseSegmentResult
    from app.pipeline.pose import LANDMARK_LEFT_SHOULDER, LANDMARK_LEFT_WRIST

    keypoints = np.zeros((30, 33, 3), dtype=np.float32)
    fake_phases = PhaseSegmentResult(
        phases={
            "setup": PhaseInfo(0, 5, 5),
            "backswing": PhaseInfo(5, 14, 10),
            "top": PhaseInfo(15, 15, 15),
            "downswing": PhaseInfo(16, 20, 18),
            "impact": PhaseInfo(21, 21, 21),
            "follow_through": PhaseInfo(22, 29, 25),
        },
        swing_start=5,
        swing_end=25,
        top_frame=15,
        impact_frame=21,
        handedness="right",
        lead_wrist_idx=LANDMARK_LEFT_WRIST,
        lead_shoulder_idx=LANDMARK_LEFT_SHOULDER,
        fps=30.0,
    )
    feats = extract_features(keypoints, fake_phases)
    assert isinstance(feats, dict)
    for name, value in feats.items():
        assert math.isfinite(value), f"{name} 非有限"
