"""P2-M7-R1 Phase B1 · pose_refine 单测。"""

from __future__ import annotations

import numpy as np

from app.pipeline.pose import (
    LANDMARK_LEFT_HIP,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_HIP,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
    NUM_LANDMARKS,
    PoseResult,
)
from app.pipeline.pose_refine import (
    BONE_LENGTH_DEVIATION_RATIO,
    apply_bone_length_visibility_penalty,
    refine_pose_keypoints,
    refine_pose_result,
)


def _flat_pose(num_frames: int = 30, fps: float = 30.0) -> PoseResult:
    kp = np.zeros((num_frames, NUM_LANDMARKS, 3), dtype=np.float32)
    vis = np.ones((num_frames, NUM_LANDMARKS), dtype=np.float32) * 0.9
    for f in range(num_frames):
        kp[f, LANDMARK_LEFT_SHOULDER] = [0.45, 0.35, 0]
        kp[f, LANDMARK_RIGHT_SHOULDER] = [0.55, 0.35, 0]
        kp[f, LANDMARK_LEFT_HIP] = [0.47, 0.58, 0]
        kp[f, LANDMARK_RIGHT_HIP] = [0.53, 0.58, 0]
        kp[f, LANDMARK_LEFT_WRIST] = [0.46, 0.62, 0]
        kp[f, LANDMARK_RIGHT_WRIST] = [0.54, 0.62, 0]
    return PoseResult(
        keypoints=kp,
        visibility=vis,
        valid_mask=np.ones(num_frames, dtype=bool),
        num_frames=num_frames,
        fps=fps,
    )


def test_bone_length_penalty_downweights_spike_frame() -> None:
    pose = _flat_pose()
    # 第 20 帧相对第 19 帧肩宽突变（模拟单帧检测跳变）
    pose.keypoints[19, LANDMARK_RIGHT_SHOULDER, 0] = 0.55
    pose.keypoints[20, LANDMARK_RIGHT_SHOULDER, 0] = 0.85
    vis_adj = apply_bone_length_visibility_penalty(pose.keypoints, pose.visibility)
    assert vis_adj[20, LANDMARK_LEFT_SHOULDER] < pose.visibility[20, LANDMARK_LEFT_SHOULDER]
    assert vis_adj[19, LANDMARK_LEFT_SHOULDER] == pose.visibility[19, LANDMARK_LEFT_SHOULDER]


def test_one_euro_smooths_wrist_jitter() -> None:
    pose = _flat_pose(num_frames=40)
    for f in range(10, 30):
        pose.keypoints[f, LANDMARK_LEFT_WRIST, 0] = 0.46 + (0.04 if f % 2 == 0 else -0.04)
    refined, _ = refine_pose_keypoints(pose.keypoints, pose.visibility, fps=pose.fps)
    raw_std = np.std(pose.keypoints[10:30, LANDMARK_LEFT_WRIST, 0])
    smooth_std = np.std(refined[10:30, LANDMARK_LEFT_WRIST, 0])
    assert smooth_std < raw_std


def test_low_visibility_frame_not_smoothed() -> None:
    pose = _flat_pose()
    pose.visibility[15, LANDMARK_LEFT_WRIST] = 0.2
    pose.keypoints[15, LANDMARK_LEFT_WRIST, 0] = 0.99
    refined, vis = refine_pose_keypoints(pose.keypoints, pose.visibility, fps=pose.fps)
    assert refined[15, LANDMARK_LEFT_WRIST, 0] == pose.keypoints[15, LANDMARK_LEFT_WRIST, 0]
    assert vis[15, LANDMARK_LEFT_WRIST] == pose.visibility[15, LANDMARK_LEFT_WRIST]


def test_refine_pose_result_preserves_valid_mask() -> None:
    pose = _flat_pose()
    pose.visibility[15, LANDMARK_LEFT_WRIST] = 0.2
    pose.keypoints[15, LANDMARK_LEFT_WRIST, 0] = 0.99
    out = refine_pose_result(pose)
    assert out.valid_mask[15] == pose.valid_mask[15]
    assert out.keypoints[15, LANDMARK_LEFT_WRIST, 0] == pose.keypoints[15, LANDMARK_LEFT_WRIST, 0]
