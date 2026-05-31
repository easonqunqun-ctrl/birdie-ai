"""P2-M7-R1 · 旋转类特征多帧轨迹（Phase A/B）。

Phase A：setup median baseline + backswing/top 窗口聚合 + sanity
Phase B2：估计器 A（肩线）/ B（胸廓 proxy）/ C（几何下界）
Phase B3：weighted_median 融合 + ``rotation_confidence``
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import numpy as np

from app.pipeline.features import _line_angle_deg, _safe_frame
from app.pipeline.pose import (
    LANDMARK_LEFT_HIP,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_RIGHT_HIP,
    LANDMARK_RIGHT_SHOULDER,
)

if TYPE_CHECKING:
    from app.pipeline.phases import PhaseSegmentResult

log = logging.getLogger("ai_engine.rotation_track")

CameraAngleLike = Literal["face_on", "down_the_line"] | None

# sanity · 与 feature_measurability 对齐
SHOULDER_ROT_MIN_SANE = 15.0
SHOULDER_ROT_MAX_SANE = 110.0
X_FACTOR_MAX_SANE = 80.0
HIP_ROT_MAX_SANE = 90.0

# 估计器 C · 几何下界
WRIST_HIGH_FOR_MIN_ROT = 0.12
MIN_PLAUSIBLE_SHOULDER_IF_WRIST_HIGH = 35.0
TOP_WINDOW_RADIUS = 5

# 融合 · kickoff §6.5
ESTIMATOR_DISAGREEMENT_DEG = 25.0
LOW_SHOULDER_VETO_DEG = 20.0
HIGH_SHOULDER_VETO_DEG = 110.0
HIGH_A_LOW_B_VETO_B = 50.0
VISIBILITY_MEAN_MIN = 0.5
WEIGHT_A_FACE_ON = 1.0
WEIGHT_B_FACE_ON = 0.85
WEIGHT_B_DTL = 0.2
BASE_CONFIDENCE = 0.85

WARN_ESTIMATOR_DISAGREEMENT = "estimator_disagreement"
WARN_ROTATION_LOW_VISIBILITY = "rotation_low_visibility"


@dataclass(frozen=True)
class RotationTrackResult:
    """三估计器 + 融合输出（kickoff §6.1）。"""

    shoulder_rotation_top: float | None
    hip_rotation_top: float | None
    x_factor: float | None
    rotation_confidence: float
    estimator_a: float | None
    estimator_b: float | None
    estimator_c_min: float | None
    quality_warnings: list[str] = field(default_factory=list)

    def as_feature_dict(self) -> dict[str, float]:
        out: dict[str, float] = {}
        if self.shoulder_rotation_top is not None:
            out["shoulder_rotation_top"] = self.shoulder_rotation_top
        if self.hip_rotation_top is not None:
            out["hip_rotation_top"] = self.hip_rotation_top
        if self.x_factor is not None:
            out["x_factor"] = self.x_factor
        return out


def _norm_angle_delta(current: float, baseline: float) -> float:
    diff = current - baseline
    diff = (diff + 180) % 360 - 180
    return abs(diff)


def _shoulder_line_angle(frame_kp: np.ndarray) -> float:
    l_sh = frame_kp[LANDMARK_LEFT_SHOULDER, :2]
    r_sh = frame_kp[LANDMARK_RIGHT_SHOULDER, :2]
    return _line_angle_deg(l_sh, r_sh)


def _hip_line_angle(frame_kp: np.ndarray) -> float:
    l_hip = frame_kp[LANDMARK_LEFT_HIP, :2]
    r_hip = frame_kp[LANDMARK_RIGHT_HIP, :2]
    return _line_angle_deg(l_hip, r_hip)


def _torso_angle_deg(frame_kp: np.ndarray) -> float:
    """Face-on 胸廓 proxy：肩中点相对髋中点的 2D 朝向（度）。"""
    mid_sh = (
        frame_kp[LANDMARK_LEFT_SHOULDER, :2] + frame_kp[LANDMARK_RIGHT_SHOULDER, :2]
    ) / 2.0
    mid_hip = (frame_kp[LANDMARK_LEFT_HIP, :2] + frame_kp[LANDMARK_RIGHT_HIP, :2]) / 2.0
    vec = mid_sh - mid_hip
    return float(math.degrees(math.atan2(vec[0], -vec[1])))


def _setup_baseline_angles(
    keypoints: np.ndarray, phases: PhaseSegmentResult
) -> tuple[float, float, float] | None:
    """setup 窗内肩线 / 髋线 / 胸廓角 median baseline。"""
    setup = phases.phases["setup"]
    lo = max(0, setup.start_frame)
    hi = min(len(keypoints) - 1, setup.end_frame)
    if hi < lo:
        kp = _safe_frame(keypoints, setup.key_frame)
        return (
            _shoulder_line_angle(kp),
            _hip_line_angle(kp),
            _torso_angle_deg(kp),
        )
    shoulder_vals: list[float] = []
    hip_vals: list[float] = []
    torso_vals: list[float] = []
    for f in range(lo, hi + 1):
        kp = keypoints[f]
        shoulder_vals.append(_shoulder_line_angle(kp))
        hip_vals.append(_hip_line_angle(kp))
        torso_vals.append(_torso_angle_deg(kp))
    if not shoulder_vals:
        return None
    return (
        float(np.median(shoulder_vals)),
        float(np.median(hip_vals)),
        float(np.median(torso_vals)),
    )


def _backswing_frame_range(phases: PhaseSegmentResult, num_frames: int) -> range:
    start = max(0, phases.swing_start)
    end = min(num_frames - 1, phases.top_frame)
    if end <= start:
        end = min(num_frames - 1, start + 1)
    return range(start, end + 1)


def _rotation_aggregate(
    keypoints: np.ndarray,
    *,
    backswing_frames: range,
    top_frame: int,
    baseline: float,
    angle_fn,
) -> float | None:
    """估计器 A 核心：backswing max 与 top±5 median 取较大值（A5）。"""
    backswing_deltas: list[float] = []
    for f in backswing_frames:
        if f < 0 or f >= len(keypoints):
            continue
        ang = angle_fn(keypoints[f])
        backswing_deltas.append(_norm_angle_delta(ang, baseline))
    if not backswing_deltas:
        return None

    max_backswing = float(max(backswing_deltas))

    top_lo = max(0, top_frame - TOP_WINDOW_RADIUS)
    top_hi = min(len(keypoints) - 1, top_frame + TOP_WINDOW_RADIUS)
    top_deltas: list[float] = []
    for f in range(top_lo, top_hi + 1):
        ang = angle_fn(keypoints[f])
        top_deltas.append(_norm_angle_delta(ang, baseline))
    if not top_deltas:
        return max_backswing

    top_median = float(np.median(top_deltas))
    return float(max(max_backswing, top_median))


def _estimator_a_shoulder(
    keypoints: np.ndarray,
    phases: PhaseSegmentResult,
    baseline_sh: float,
    frames: range,
) -> float | None:
    return _rotation_aggregate(
        keypoints,
        backswing_frames=frames,
        top_frame=phases.top_frame,
        baseline=baseline_sh,
        angle_fn=_shoulder_line_angle,
    )


def _estimator_b_torso(
    keypoints: np.ndarray,
    phases: PhaseSegmentResult,
    baseline_torso: float,
    frames: range,
) -> float | None:
    """估计器 B · 胸廓朝向相对 setup 的最大变化（度）。"""
    deltas: list[float] = []
    for f in frames:
        if f < 0 or f >= len(keypoints):
            continue
        ang = _torso_angle_deg(keypoints[f])
        deltas.append(_norm_angle_delta(ang, baseline_torso))
    if not deltas:
        return None
    top_lo = max(0, phases.top_frame - TOP_WINDOW_RADIUS)
    top_hi = min(len(keypoints) - 1, phases.top_frame + TOP_WINDOW_RADIUS)
    top_deltas = [
        _norm_angle_delta(_torso_angle_deg(keypoints[f]), baseline_torso)
        for f in range(top_lo, top_hi + 1)
    ]
    return float(max(max(deltas), float(np.median(top_deltas)) if top_deltas else 0.0))


def _estimator_c_min(existing_features: dict[str, float] | None) -> float | None:
    """估计器 C · 几何下界（高腕位时肩转不应极低）。"""
    feats = existing_features or {}
    wrist = feats.get("top_wrist_position")
    if wrist is None or wrist < WRIST_HIGH_FOR_MIN_ROT:
        return None
    arm = feats.get("left_arm_straightness")
    if arm is not None and arm < 120.0:
        return None
    return MIN_PLAUSIBLE_SHOULDER_IF_WRIST_HIGH


def _shoulder_visibility_mean(
    visibility: np.ndarray | None,
    keypoints: np.ndarray,
    phases: PhaseSegmentResult,
) -> float:
    if visibility is None:
        return 0.9
    frames = _backswing_frame_range(phases, len(keypoints))
    vals: list[float] = []
    for f in frames:
        vals.append(float(visibility[f, LANDMARK_LEFT_SHOULDER]))
        vals.append(float(visibility[f, LANDMARK_RIGHT_SHOULDER]))
    return float(np.mean(vals)) if vals else 0.0


def _weighted_median(values: list[float], weights: list[float]) -> float:
    pairs = sorted(zip(values, weights, strict=True), key=lambda x: x[0])
    total = float(sum(weights))
    if total <= 0:
        return float(np.median(values))
    cumulative = 0.0
    for value, weight in pairs:
        cumulative += weight
        if cumulative >= total / 2.0:
            return value
    return pairs[-1][0]


def _apply_x_factor_sanity(
    shoulder: float | None,
    hip: float | None,
) -> tuple[float | None, float | None, float | None]:
    if shoulder is None or hip is None:
        return shoulder, hip, None
    if hip > HIP_ROT_MAX_SANE:
        return shoulder, None, None
    x_factor = max(0.0, shoulder - hip)
    if x_factor > X_FACTOR_MAX_SANE:
        return None, None, None
    return shoulder, hip, x_factor


def fuse_rotation_estimators(
    *,
    estimator_a: float | None,
    estimator_b: float | None,
    estimator_c_min: float | None,
    hip_rotation: float | None,
    camera_angle: CameraAngleLike,
    visibility_mean: float,
) -> RotationTrackResult:
    """B3 · 融合 A/B/C + ``rotation_confidence``（kickoff §6.5）。"""
    warnings: list[str] = []
    conf = BASE_CONFIDENCE

    if visibility_mean < VISIBILITY_MEAN_MIN:
        return RotationTrackResult(
            None,
            None,
            None,
            0.0,
            estimator_a,
            estimator_b,
            estimator_c_min,
            [WARN_ROTATION_LOW_VISIBILITY],
        )

    if camera_angle == "down_the_line":
        return RotationTrackResult(
            None,
            None,
            None,
            0.0,
            estimator_a,
            estimator_b,
            estimator_c_min,
            warnings,
        )

    a = estimator_a
    b = estimator_b
    c_min = estimator_c_min

    if a is not None and a < LOW_SHOULDER_VETO_DEG and c_min is not None and c_min > a:
        a = None
        conf *= 0.7

    if (
        a is not None
        and a > HIGH_SHOULDER_VETO_DEG
        and b is not None
        and b < HIGH_A_LOW_B_VETO_B
    ):
        a = None
        conf *= 0.7

    w_b = WEIGHT_B_FACE_ON if camera_angle == "face_on" else WEIGHT_B_DTL
    shoulder: float | None = None

    if a is not None and b is not None:
        if abs(a - b) > ESTIMATOR_DISAGREEMENT_DEG:
            conf *= 0.6
            warnings.append(WARN_ESTIMATOR_DISAGREEMENT)
        shoulder = _weighted_median([a, b], [WEIGHT_A_FACE_ON, w_b])
    elif a is not None:
        shoulder = a
        conf *= 0.92
    elif b is not None:
        shoulder = b
        conf *= 0.75

    if shoulder is not None and (
        shoulder < SHOULDER_ROT_MIN_SANE or shoulder > SHOULDER_ROT_MAX_SANE
    ):
        shoulder = None
        conf = 0.0

    hip = hip_rotation
    shoulder, hip, x_factor = _apply_x_factor_sanity(shoulder, hip)

    return RotationTrackResult(
        shoulder,
        hip,
        x_factor,
        min(max(conf, 0.0), 1.0),
        estimator_a,
        estimator_b,
        estimator_c_min,
        warnings,
    )


def compute_rotation_track(
    keypoints: np.ndarray,
    phases: PhaseSegmentResult,
    *,
    visibility: np.ndarray | None = None,
    camera_angle: CameraAngleLike = None,
    existing_features: dict[str, float] | None = None,
) -> RotationTrackResult:
    """三估计器 + 融合；DTL 下旋转维为 None。"""
    baselines = _setup_baseline_angles(keypoints, phases)
    if baselines is None:
        return RotationTrackResult(
            None,
            None,
            None,
            0.0,
            None,
            None,
            _estimator_c_min(existing_features),
            [],
        )

    baseline_sh, baseline_hip, baseline_torso = baselines
    frames = _backswing_frame_range(phases, len(keypoints))

    est_a = _estimator_a_shoulder(keypoints, phases, baseline_sh, frames)
    est_b = _estimator_b_torso(keypoints, phases, baseline_torso, frames)
    est_c = _estimator_c_min(existing_features)
    hip = _rotation_aggregate(
        keypoints,
        backswing_frames=frames,
        top_frame=phases.top_frame,
        baseline=baseline_hip,
        angle_fn=_hip_line_angle,
    )

    vis_mean = _shoulder_visibility_mean(visibility, keypoints, phases)
    return fuse_rotation_estimators(
        estimator_a=est_a,
        estimator_b=est_b,
        estimator_c_min=est_c,
        hip_rotation=hip,
        camera_angle=camera_angle,
        visibility_mean=vis_mean,
    )


def compute_rotation_features(
    keypoints: np.ndarray,
    phases: PhaseSegmentResult,
    *,
    existing_features: dict[str, float] | None = None,
    camera_angle: CameraAngleLike = None,
    visibility: np.ndarray | None = None,
) -> dict[str, float | None]:
    """兼容 Phase A 测试入口。"""
    result = compute_rotation_track(
        keypoints,
        phases,
        visibility=visibility,
        camera_angle=camera_angle,
        existing_features=existing_features,
    )
    return {
        "shoulder_rotation_top": result.shoulder_rotation_top,
        "hip_rotation_top": result.hip_rotation_top,
        "x_factor": result.x_factor,
    }


def apply_rotation_track(
    features: dict[str, float],
    keypoints: np.ndarray,
    phases: PhaseSegmentResult,
    *,
    visibility: np.ndarray | None = None,
    camera_angle: CameraAngleLike = None,
    track_result_out: list[RotationTrackResult] | None = None,
) -> dict[str, float]:
    """用融合旋转结果覆盖 features；可选回传 ``RotationTrackResult``。"""
    result = compute_rotation_track(
        keypoints,
        phases,
        visibility=visibility,
        camera_angle=camera_angle,
        existing_features=features,
    )
    if track_result_out is not None:
        track_result_out.append(result)

    out = dict(features)
    for key in ("shoulder_rotation_top", "hip_rotation_top", "x_factor"):
        out.pop(key, None)
    out.update(result.as_feature_dict())
    return out
