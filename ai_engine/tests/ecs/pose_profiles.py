"""ECS v1 CI 回归用合成 Pose 配置（非授权顶尖素材，仅 scoring 漂移门禁）。"""

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


def _lerp(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    return a + (b - a) * t


def _ideal_keyframes() -> tuple[dict[int, np.ndarray], int]:
    num_frames = 90
    f_setup, f_top, f_impact, f_finish = 10, 45, 65, 85

    def setup_kp() -> np.ndarray:
        kp = np.zeros((NUM_LANDMARKS, 3), dtype=np.float32)
        kp[LANDMARK_NOSE] = [0.50, 0.25, 0]
        kp[LANDMARK_LEFT_SHOULDER] = [0.45, 0.35, 0]
        kp[LANDMARK_RIGHT_SHOULDER] = [0.55, 0.35, 0]
        kp[LANDMARK_LEFT_ELBOW] = [0.42, 0.50, 0]
        kp[LANDMARK_RIGHT_ELBOW] = [0.58, 0.50, 0]
        kp[LANDMARK_LEFT_WRIST] = [0.46, 0.62, 0]
        kp[LANDMARK_RIGHT_WRIST] = [0.54, 0.62, 0]
        kp[LANDMARK_LEFT_HIP] = [0.47, 0.58, 0]
        kp[LANDMARK_RIGHT_HIP] = [0.53, 0.58, 0]
        kp[LANDMARK_LEFT_KNEE] = [0.47, 0.73, 0]
        kp[LANDMARK_RIGHT_KNEE] = [0.53, 0.73, 0]
        kp[LANDMARK_LEFT_ANKLE] = [0.47, 0.90, 0]
        kp[LANDMARK_RIGHT_ANKLE] = [0.53, 0.90, 0]
        return kp

    def top_kp() -> np.ndarray:
        kp = setup_kp().copy()
        kp[LANDMARK_LEFT_WRIST] = [0.40, 0.10, 0]
        kp[LANDMARK_RIGHT_WRIST] = [0.42, 0.12, 0]
        kp[LANDMARK_LEFT_ELBOW] = [0.42, 0.25, 0]
        kp[LANDMARK_RIGHT_ELBOW] = [0.50, 0.28, 0]
        kp[LANDMARK_LEFT_SHOULDER] = [0.48, 0.45, 0]
        kp[LANDMARK_RIGHT_SHOULDER] = [0.60, 0.25, 0]
        kp[LANDMARK_LEFT_HIP] = [0.48, 0.60, 0]
        kp[LANDMARK_RIGHT_HIP] = [0.54, 0.56, 0]
        return kp

    def impact_kp() -> np.ndarray:
        kp = setup_kp().copy()
        kp[LANDMARK_LEFT_WRIST] = [0.48, 0.63, 0]
        kp[LANDMARK_RIGHT_WRIST] = [0.52, 0.63, 0]
        kp[LANDMARK_LEFT_HIP] = [0.45, 0.58, 0]
        kp[LANDMARK_RIGHT_HIP] = [0.56, 0.58, 0]
        kp[LANDMARK_LEFT_SHOULDER] = [0.46, 0.37, 0]
        kp[LANDMARK_RIGHT_SHOULDER] = [0.55, 0.36, 0]
        return kp

    def finish_kp() -> np.ndarray:
        kp = impact_kp().copy()
        kp[LANDMARK_LEFT_WRIST] = [0.45, 0.20, 0]
        kp[LANDMARK_RIGHT_WRIST] = [0.50, 0.22, 0]
        kp[LANDMARK_LEFT_ELBOW] = [0.45, 0.30, 0]
        kp[LANDMARK_RIGHT_ELBOW] = [0.52, 0.30, 0]
        return kp

    keypoints = np.zeros((num_frames, NUM_LANDMARKS, 3), dtype=np.float32)
    keypoints[f_setup] = setup_kp()
    keypoints[f_top] = top_kp()
    keypoints[f_impact] = impact_kp()
    keypoints[f_finish] = finish_kp()

    for f in range(0, f_setup):
        keypoints[f] = keypoints[f_setup]
    for f in range(f_setup + 1, f_top):
        t = (f - f_setup) / (f_top - f_setup)
        keypoints[f] = _lerp(keypoints[f_setup], keypoints[f_top], t)
    for f in range(f_top + 1, f_impact):
        t = (f - f_top) / (f_impact - f_top)
        keypoints[f] = _lerp(keypoints[f_top], keypoints[f_impact], t)
    for f in range(f_impact + 1, f_finish):
        t = (f - f_impact) / (f_finish - f_impact)
        keypoints[f] = _lerp(keypoints[f_impact], keypoints[f_finish], t)
    for f in range(f_finish + 1, num_frames):
        keypoints[f] = keypoints[f_finish]

    return {
        f_setup: keypoints[f_setup],
        f_top: keypoints[f_top],
        f_impact: keypoints[f_impact],
        f_finish: keypoints[f_finish],
    }, num_frames


def build_pose_profile(profile: str) -> PoseResult:
    """profile 名与 manifest.pose_profile 对齐。"""
    if profile == "ideal_swing":
        frames, num_frames = _ideal_keyframes()
        return _build_from_frames(frames, num_frames)
    if profile == "early_extension_swing":
        pose = build_pose_profile("ideal_swing")
        hip_shift = np.array([0.04, 0.06, 0], dtype=np.float32)
        for idx in (45, 55, 65):
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


def _build_from_frames(keyframes: dict[int, np.ndarray], num_frames: int) -> PoseResult:
    f_setup, f_top, f_impact, f_finish = 10, 45, 65, 85
    keypoints = np.zeros((num_frames, NUM_LANDMARKS, 3), dtype=np.float32)
    keypoints[f_setup] = keyframes[f_setup]
    keypoints[f_top] = keyframes[f_top]
    keypoints[f_impact] = keyframes[f_impact]
    keypoints[f_finish] = keyframes[f_finish]

    for f in range(0, f_setup):
        keypoints[f] = keypoints[f_setup]
    for f in range(f_setup + 1, f_top):
        t = (f - f_setup) / (f_top - f_setup)
        keypoints[f] = _lerp(keypoints[f_setup], keypoints[f_top], t)
    for f in range(f_top + 1, f_impact):
        t = (f - f_top) / (f_impact - f_top)
        keypoints[f] = _lerp(keypoints[f_top], keypoints[f_impact], t)
    for f in range(f_impact + 1, f_finish):
        t = (f - f_impact) / (f_finish - f_impact)
        keypoints[f] = _lerp(keypoints[f_impact], keypoints[f_finish], t)
    for f in range(f_finish + 1, num_frames):
        keypoints[f] = keypoints[f_finish]

    visibility = np.ones((num_frames, NUM_LANDMARKS), dtype=np.float32) * 0.9
    return PoseResult(
        keypoints=keypoints,
        visibility=visibility,
        valid_mask=np.ones(num_frames, dtype=bool),
        num_frames=num_frames,
        fps=30.0,
    )
