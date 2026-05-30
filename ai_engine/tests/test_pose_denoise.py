"""Pose 时域降噪单测。"""

from __future__ import annotations

import numpy as np

from app.pipeline.pose_denoise import denoise_pose_keypoints


def test_denoise_smooths_spike() -> None:
    n, l = 10, 3
    kp = np.zeros((n, l, 3), dtype=np.float32)
    vis = np.ones((n, l), dtype=np.float32) * 0.9
    kp[:, 0, 0] = 0.5
    kp[5, 0, 0] = 0.95  # 单帧尖峰
    out = denoise_pose_keypoints(kp, vis, window=5)
    assert abs(out[5, 0, 0] - 0.95) < abs(kp[5, 0, 0] - 0.95)
    assert 0.5 < out[5, 0, 0] < 0.95
