"""Pose 关键点时域降噪（P2 评分护城河 v0.3）。

MediaPipe 已开 ``smooth_landmarks=True``，但在 office/转播/遮挡场景仍会有单帧跳变。
对 x/y 做 visibility 加权滑动平均，再交给特征抽取，减少「噪音帧」拉偏分数。
"""

from __future__ import annotations

import numpy as np

from app.pipeline.pose import PoseResult


def denoise_pose_keypoints(
    keypoints: np.ndarray,
    visibility: np.ndarray,
    *,
    window: int = 5,
) -> np.ndarray:
    """对 (F, L, 3) 关键点做轻度时域平滑；仅平滑 x/y，保留 z。"""
    if keypoints.ndim != 3 or len(keypoints) < 2:
        return keypoints
    out = keypoints.copy()
    n_frames = out.shape[0]
    half = max(1, window // 2)
    for i in range(n_frames):
        lo = max(0, i - half)
        hi = min(n_frames, i + half + 1)
        for lm in range(out.shape[1]):
            w = visibility[lo:hi, lm]
            if float(w.sum()) < 1e-6:
                continue
            for c in range(2):
                vals = keypoints[lo:hi, lm, c]
                out[i, lm, c] = float(np.average(vals, weights=w))
    return out


def denoise_pose_result(pose: PoseResult, *, window: int = 5) -> PoseResult:
    """返回新 PoseResult（不原地改输入）。"""
    kp = denoise_pose_keypoints(pose.keypoints, pose.visibility, window=window)
    return PoseResult(
        keypoints=kp,
        visibility=pose.visibility,
        fps=pose.fps,
        num_frames=pose.num_frames,
        valid_mask=pose.valid_mask,
    )
