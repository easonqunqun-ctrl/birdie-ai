"""ECS v1 CI 回归用合成 Pose 配置（非授权顶尖素材，仅 scoring 漂移门禁）。

v1.2.4：标定 ideal_swing 使 teaching 标杆 overall ≥80；新增 amateur_solid 业余良好样本。
"""

from __future__ import annotations

import numpy as np

from app.pipeline.pose import (
    LANDMARK_LEFT_ANKLE,
    LANDMARK_LEFT_ELBOW,
    LANDMARK_LEFT_HIP,
    LANDMARK_LEFT_KNEE,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_NOSE,
    LANDMARK_RIGHT_ANKLE,
    LANDMARK_RIGHT_ELBOW,
    LANDMARK_RIGHT_HIP,
    LANDMARK_RIGHT_KNEE,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
    NUM_LANDMARKS,
    PoseResult,
)

F_SETUP, F_TOP, F_IMPACT, F_FINISH = 10, 45, 65, 85
NUM_FRAMES = 90

_UPPER_BODY = (
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_LEFT_ELBOW,
    LANDMARK_RIGHT_ELBOW,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_WRIST,
    LANDMARK_NOSE,
)
_LOWER_BODY = (
    LANDMARK_LEFT_HIP,
    LANDMARK_RIGHT_HIP,
    LANDMARK_LEFT_KNEE,
    LANDMARK_RIGHT_KNEE,
    LANDMARK_LEFT_ANKLE,
    LANDMARK_RIGHT_ANKLE,
)


def _lerp(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    return a + (b - a) * t


def _blank_keyframe() -> np.ndarray:
    return np.zeros((NUM_LANDMARKS, 3), dtype=np.float32)


def _apply_landmarks(kp: np.ndarray, pairs: dict[int, tuple[float, float]]) -> None:
    for idx, (x, y) in pairs.items():
        kp[idx, 0] = x
        kp[idx, 1] = y


def _setup_keyframe() -> np.ndarray:
    """准备位：脊柱前倾 ~30°，膝弯 ~155°（对齐 docs/05 ideal 区间）。"""
    kp = _blank_keyframe()
    _apply_landmarks(
        kp,
        {
            LANDMARK_NOSE: (0.55, 0.22),
            LANDMARK_LEFT_SHOULDER: (0.56, 0.34),
            LANDMARK_RIGHT_SHOULDER: (0.68, 0.34),
            LANDMARK_LEFT_ELBOW: (0.50, 0.48),
            LANDMARK_RIGHT_ELBOW: (0.70, 0.48),
            LANDMARK_LEFT_WRIST: (0.52, 0.60),
            LANDMARK_RIGHT_WRIST: (0.66, 0.60),
            LANDMARK_LEFT_HIP: (0.44, 0.58),
            LANDMARK_RIGHT_HIP: (0.52, 0.58),
            LANDMARK_LEFT_KNEE: (0.52, 0.71),
            LANDMARK_RIGHT_KNEE: (0.56, 0.73),
            LANDMARK_LEFT_ANKLE: (0.47, 0.90),
            LANDMARK_RIGHT_ANKLE: (0.53, 0.90),
        },
    )
    return kp


def _top_keyframe() -> np.ndarray:
    """上杆顶点：肩旋转 ~90°、髋 ~45°、X-Factor ~45°。"""
    kp = _blank_keyframe()
    _apply_landmarks(
        kp,
        {
            LANDMARK_NOSE: (0.52, 0.18),
            LANDMARK_LEFT_SHOULDER: (0.32, 0.28),
            LANDMARK_RIGHT_SHOULDER: (0.56, 0.44),
            LANDMARK_LEFT_ELBOW: (0.28, 0.16),
            LANDMARK_RIGHT_ELBOW: (0.44, 0.20),
            LANDMARK_LEFT_WRIST: (0.26, 0.06),
            LANDMARK_RIGHT_WRIST: (0.38, 0.08),
            LANDMARK_LEFT_HIP: (0.40, 0.60),
            LANDMARK_RIGHT_HIP: (0.50, 0.56),
            LANDMARK_LEFT_KNEE: (0.52, 0.71),
            LANDMARK_RIGHT_KNEE: (0.56, 0.73),
            LANDMARK_LEFT_ANKLE: (0.47, 0.90),
            LANDMARK_RIGHT_ANKLE: (0.53, 0.90),
        },
    )
    return kp


def _impact_keyframe() -> np.ndarray:
    """击球：脊柱与准备位接近；前臂相对 top 释放。"""
    kp = _setup_keyframe()
    _apply_landmarks(
        kp,
        {
            LANDMARK_LEFT_ELBOW: (0.50, 0.52),
            LANDMARK_RIGHT_ELBOW: (0.64, 0.50),
            LANDMARK_LEFT_WRIST: (0.56, 0.64),
            LANDMARK_RIGHT_WRIST: (0.60, 0.62),
        },
    )
    return kp


def _finish_keyframe() -> np.ndarray:
    kp = _impact_keyframe()
    _apply_landmarks(
        kp,
        {
            LANDMARK_NOSE: (0.50, 0.24),
            LANDMARK_LEFT_WRIST: (0.48, 0.24),
            LANDMARK_RIGHT_WRIST: (0.52, 0.26),
            LANDMARK_LEFT_ELBOW: (0.46, 0.32),
            LANDMARK_RIGHT_ELBOW: (0.54, 0.32),
        },
    )
    return kp


def _blend_keyframe(
    top: np.ndarray,
    target: np.ndarray,
    upper_t: float,
    lower_t: float,
) -> np.ndarray:
    out = top.copy()
    for idx in _UPPER_BODY:
        out[idx] = _lerp(top[idx], target[idx], upper_t)
    for idx in _LOWER_BODY:
        out[idx] = _lerp(top[idx], target[idx], lower_t)
    return out


def _build_ideal_keypoints() -> np.ndarray:
    setup = _setup_keyframe()
    top = _top_keyframe()
    impact = _impact_keyframe()
    finish = _finish_keyframe()

    keypoints = np.zeros((NUM_FRAMES, NUM_LANDMARKS, 3), dtype=np.float32)
    keypoints[F_SETUP] = setup
    keypoints[F_TOP] = top
    keypoints[F_IMPACT] = impact
    keypoints[F_FINISH] = finish

    for f in range(0, F_SETUP + 1):
        keypoints[f] = setup
    for f in range(F_SETUP + 1, F_TOP):
        t = (f - F_SETUP) / (F_TOP - F_SETUP)
        keypoints[f] = _lerp(setup, top, t)

    hip_lead_until = 52
    for f in range(F_TOP + 1, F_IMPACT + 1):
        if f <= hip_lead_until:
            hip_t = (f - F_TOP) / max(1, hip_lead_until - F_TOP)
            upper_t = 0.0
        else:
            hip_t = 1.0
            upper_t = (f - hip_lead_until) / max(1, F_IMPACT - hip_lead_until)
        keypoints[f] = _blend_keyframe(top, impact, upper_t=upper_t, lower_t=hip_t)

    for f in range(F_IMPACT + 1, F_FINISH):
        t = (f - F_IMPACT) / (F_FINISH - F_IMPACT)
        keypoints[f] = _lerp(impact, finish, t)
    for f in range(F_FINISH, NUM_FRAMES):
        keypoints[f] = finish

    return keypoints


def _pose_from_keypoints(keypoints: np.ndarray) -> PoseResult:
    visibility = np.ones((NUM_FRAMES, NUM_LANDMARKS), dtype=np.float32) * 0.9
    return PoseResult(
        keypoints=keypoints,
        visibility=visibility,
        valid_mask=np.ones(NUM_FRAMES, dtype=bool),
        num_frames=NUM_FRAMES,
        fps=30.0,
    )


def build_pose_profile(profile: str) -> PoseResult:
    """profile 名与 manifest.pose_profile 对齐。"""
    if profile == "ideal_swing":
        return _pose_from_keypoints(_build_ideal_keypoints())

    if profile == "amateur_solid":
        keypoints = _build_ideal_keypoints().copy()
        # 业余良好：略欠肩旋转与释放时机，overall 目标 70–78
        for idx in range(F_TOP, F_IMPACT + 1):
            keypoints[idx, LANDMARK_LEFT_SHOULDER, 0] += 0.04
            keypoints[idx, LANDMARK_RIGHT_SHOULDER, 0] += 0.04
        return _pose_from_keypoints(keypoints)

    if profile == "early_extension_swing":
        pose = build_pose_profile("ideal_swing")
        hip_shift = np.array([0.04, 0.06, 0], dtype=np.float32)
        for idx in (F_TOP, 55, F_IMPACT):
            pose.keypoints[idx, LANDMARK_LEFT_HIP] = pose.keypoints[idx, LANDMARK_LEFT_HIP] + hip_shift
            pose.keypoints[idx, LANDMARK_RIGHT_HIP] = pose.keypoints[idx, LANDMARK_RIGHT_HIP] + hip_shift
        return pose

    if profile == "sway_swing":
        pose = build_pose_profile("ideal_swing")
        sway = np.array([0.08, 0.0, 0], dtype=np.float32)
        for idx in (10, 20, 30, 40):
            pose.keypoints[idx, LANDMARK_LEFT_HIP] = pose.keypoints[idx, LANDMARK_LEFT_HIP] + sway
            pose.keypoints[idx, LANDMARK_RIGHT_HIP] = pose.keypoints[idx, LANDMARK_RIGHT_HIP] + sway
        return pose

    raise KeyError(f"unknown pose profile: {profile}")
