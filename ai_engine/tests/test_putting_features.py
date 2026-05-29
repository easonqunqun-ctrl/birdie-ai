"""P2-M7-11 W22 · 推杆 4 特征单测。

合成关键点 + 手搭 ``PuttingPhaseResult``，不依赖真分割（分割本体 W23）。
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.pipeline.pose import (
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_NOSE,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
)
from app.pipeline.putting.constants import (
    PUTTING_FEATURE_WEIGHTS,
    PUTTING_FEATURES,
    PUTTING_PHASE_WEIGHTS,
)
from app.pipeline.putting.features import extract_putting_features
from app.pipeline.putting.phases import (
    PuttingPhaseInfo,
    PuttingPhaseResult,
)

_N = 40


def _make_phases() -> PuttingPhaseResult:
    """backstroke 20 帧 / forward 10 帧 → tempo=2.0。"""
    return PuttingPhaseResult(
        phases={
            "setup": PuttingPhaseInfo(0, 4, 2),
            "backstroke": PuttingPhaseInfo(5, 25, 15),
            "impact": PuttingPhaseInfo(35, 35, 35),
            "follow": PuttingPhaseInfo(36, 39, 38),
        },
        impact_frame=35,
        swing_start=5,
        swing_end=39,
        lead_wrist_idx=LANDMARK_LEFT_WRIST,
        lead_shoulder_idx=LANDMARK_LEFT_SHOULDER,
        handedness="right",
        fps=30.0,
    )


def _make_keypoints() -> np.ndarray:
    """理想推击：肩/头全程不动，主腕沿 x 平移（钟摆方向），击球帧双腕连线竖直（方正）。"""
    kp = np.zeros((_N, 33, 3), dtype=np.float32)
    kp[:, :, 2] = 1.0  # visibility
    kp[:, LANDMARK_LEFT_SHOULDER, :2] = (0.45, 0.40)
    kp[:, LANDMARK_RIGHT_SHOULDER, :2] = (0.55, 0.40)
    kp[:, LANDMARK_NOSE, :2] = (0.50, 0.25)
    xs = np.linspace(0.40, 0.60, _N, dtype=np.float32)
    kp[:, LANDMARK_LEFT_WRIST, 0] = xs
    kp[:, LANDMARK_LEFT_WRIST, 1] = 0.50
    kp[:, LANDMARK_RIGHT_WRIST, 0] = xs  # 与左腕同 x → 连线竖直
    kp[:, LANDMARK_RIGHT_WRIST, 1] = 0.60
    return kp


def test_extract_returns_4_finite_features() -> None:
    feats = extract_putting_features(_make_keypoints(), _make_phases())
    assert set(feats) == {f["name"] for f in PUTTING_FEATURES}
    for name, value in feats.items():
        assert isinstance(value, float) and math.isfinite(value), name


def test_pendulum_stability_zero_when_shoulders_still() -> None:
    feats = extract_putting_features(_make_keypoints(), _make_phases())
    assert feats["pendulum_stability"] < 1e-9


def test_pendulum_stability_grows_with_shoulder_jitter() -> None:
    kp = _make_keypoints()
    rng = np.random.default_rng(0)
    kp[:, LANDMARK_LEFT_SHOULDER, 1] += rng.normal(0, 0.02, _N).astype(np.float32)
    kp[:, LANDMARK_RIGHT_SHOULDER, 1] += rng.normal(0, 0.02, _N).astype(np.float32)
    feats = extract_putting_features(kp, _make_phases())
    assert feats["pendulum_stability"] > 1e-5


def test_head_stability_zero_when_nose_still() -> None:
    feats = extract_putting_features(_make_keypoints(), _make_phases())
    assert feats["head_stability"] < 1e-9


def test_head_stability_grows_when_head_moves() -> None:
    kp = _make_keypoints()
    kp[:, LANDMARK_NOSE, 0] = np.linspace(0.50, 0.58, _N, dtype=np.float32)
    feats = extract_putting_features(kp, _make_phases())
    assert feats["head_stability"] > 1e-4


def test_face_alignment_near_zero_when_square() -> None:
    """双腕连线竖直 ⊥ x 向击球方向 → 方正 → ~0°。"""
    feats = extract_putting_features(_make_keypoints(), _make_phases())
    assert feats["face_alignment"] < 0.5


def test_face_alignment_near_90_when_hand_line_parallel_to_stroke() -> None:
    """双腕连线与击球方向平行 → 最不方正 → ~90°。"""
    kp = _make_keypoints()
    # 让右腕在击球帧落在左腕的 x 正前方（连线沿 x，与击球方向平行）
    kp[35, LANDMARK_RIGHT_WRIST, 0] = kp[35, LANDMARK_LEFT_WRIST, 0] + 0.1
    kp[35, LANDMARK_RIGHT_WRIST, 1] = kp[35, LANDMARK_LEFT_WRIST, 1]
    feats = extract_putting_features(kp, _make_phases())
    assert feats["face_alignment"] > 85.0


def test_tempo_ratio_matches_phase_durations() -> None:
    """backstroke 20 帧 / forward 10 帧 = 2.0。"""
    feats = extract_putting_features(_make_keypoints(), _make_phases())
    assert feats["tempo_ratio"] == pytest.approx(2.0, abs=1e-6)


def test_degenerate_input_falls_back_to_ideal_midpoints() -> None:
    """空挥动窗口 + 退化阶段 → 全部退化为 ideal 中点，不崩。"""
    kp = np.zeros((10, 33, 3), dtype=np.float32)
    phases = PuttingPhaseResult(
        phases={
            "setup": PuttingPhaseInfo(0, 0, 0),
            "backstroke": PuttingPhaseInfo(0, 0, 0),
            "impact": PuttingPhaseInfo(0, 0, 0),
            "follow": PuttingPhaseInfo(0, 0, 0),
        },
        impact_frame=0,
        swing_start=5,
        swing_end=5,  # 空窗口
        lead_wrist_idx=LANDMARK_LEFT_WRIST,
        lead_shoulder_idx=LANDMARK_LEFT_SHOULDER,
        handedness="right",
        fps=30.0,
    )
    feats = extract_putting_features(kp, phases)
    for meta in PUTTING_FEATURES:
        mid = (meta["ideal_min"] + meta["ideal_max"]) / 2.0
        assert feats[meta["name"]] == pytest.approx(mid)


def test_phase_result_rejects_missing_phase() -> None:
    with pytest.raises(ValueError, match="缺阶段"):
        PuttingPhaseResult(
            phases={"setup": PuttingPhaseInfo(0, 1, 0)},
            impact_frame=0,
            swing_start=0,
            swing_end=1,
            lead_wrist_idx=LANDMARK_LEFT_WRIST,
            lead_shoulder_idx=LANDMARK_LEFT_SHOULDER,
            handedness="right",
            fps=30.0,
        )


def test_weights_sum_to_one() -> None:
    assert sum(PUTTING_PHASE_WEIGHTS.values()) == pytest.approx(1.0)
    assert sum(PUTTING_FEATURE_WEIGHTS.values()) == pytest.approx(1.0)
