"""P2-M7-R1 Phase B1 · pose 时序 refine：骨长约束 + One Euro 滤波。

接在 ``denoise_pose_result`` 之后、``segment_phases`` 之前：
- 髋宽/肩宽 **帧间 spike** >25% → 对应 landmark visibility 降权（不用 setup 肩宽 baseline，避免 DTL 转肩误伤）
- 肩/髋/腕 x,y One Euro 滤波
- visibility < 0.5 的帧不参与滤波更新；**不修改** ``valid_mask``（阶段分割仍用 pose 原始有效帧）
"""

from __future__ import annotations

import math

import numpy as np

from app.pipeline.pose import (
    LANDMARK_LEFT_HIP,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_HIP,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
    PoseResult,
)

# kickoff B1
BONE_LENGTH_DEVIATION_RATIO = 0.25
VISIBILITY_INVALID = 0.5
BONE_PENALTY_FACTOR = 0.25

REFINE_LANDMARKS = (
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_LEFT_HIP,
    LANDMARK_RIGHT_HIP,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_WRIST,
)

_BONE_SEGMENTS: tuple[tuple[int, int, tuple[int, ...]], ...] = (
    (LANDMARK_LEFT_SHOULDER, LANDMARK_RIGHT_SHOULDER, (LANDMARK_LEFT_SHOULDER, LANDMARK_RIGHT_SHOULDER)),
    (LANDMARK_LEFT_HIP, LANDMARK_RIGHT_HIP, (LANDMARK_LEFT_HIP, LANDMARK_RIGHT_HIP)),
)


def _dist2d(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a[:2] - b[:2]))


def _segment_width(keypoints: np.ndarray, left: int, right: int) -> float:
    return _dist2d(keypoints[left, :2], keypoints[right, :2])


class _OneEuroFilter:
    """1D One Euro filter（Casiez et al.）。"""

    def __init__(
        self,
        *,
        freq: float,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ) -> None:
        self.freq = max(freq, 1.0)
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x_prev: float | None = None
        self._dx_prev = 0.0

    @staticmethod
    def _alpha(cutoff: float, te: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float) -> float:
        te = 1.0 / self.freq
        if self._x_prev is None:
            self._x_prev = x
            self._dx_prev = 0.0
            return x
        dx = (x - self._x_prev) * self.freq
        a_d = self._alpha(self.d_cutoff, te)
        dx_hat = a_d * dx + (1.0 - a_d) * self._dx_prev
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, te)
        x_hat = a * x + (1.0 - a) * self._x_prev
        self._x_prev = x_hat
        self._dx_prev = dx_hat
        return x_hat


def apply_bone_length_visibility_penalty(
    keypoints: np.ndarray,
    visibility: np.ndarray,
) -> np.ndarray:
    """帧间骨长 spike 降权（检测单帧跳变，非 sustained DTL 投影变化）。"""
    out = visibility.astype(np.float32, copy=True)
    n = len(keypoints)
    if n < 2:
        return out

    for f in range(1, n):
        prev_kp = keypoints[f - 1]
        cur_kp = keypoints[f]
        for left, right, landmarks in _BONE_SEGMENTS:
            w_prev = _segment_width(prev_kp, left, right)
            w_cur = _segment_width(cur_kp, left, right)
            if w_prev > 1e-5 and abs(w_cur - w_prev) / w_prev > BONE_LENGTH_DEVIATION_RATIO:
                for lm in landmarks:
                    out[f, lm] *= BONE_PENALTY_FACTOR
    return out


def refine_pose_keypoints(
    keypoints: np.ndarray,
    visibility: np.ndarray,
    *,
    fps: float,
) -> tuple[np.ndarray, np.ndarray]:
    """骨长 spike 降权 + One Euro 滤波；低 visibility 帧不更新滤波状态。"""
    if keypoints.ndim != 3 or len(keypoints) < 2:
        return keypoints, visibility

    vis_adj = apply_bone_length_visibility_penalty(keypoints, visibility)
    out = keypoints.copy()
    freq = max(float(fps), 1.0)

    for lm in REFINE_LANDMARKS:
        fx = _OneEuroFilter(freq=freq)
        fy = _OneEuroFilter(freq=freq)
        for f in range(len(out)):
            if float(vis_adj[f, lm]) < VISIBILITY_INVALID:
                continue
            out[f, lm, 0] = fx.filter(float(keypoints[f, lm, 0]))
            out[f, lm, 1] = fy.filter(float(keypoints[f, lm, 1]))

    return out, vis_adj


def refine_pose_result(pose: PoseResult) -> PoseResult:
    """返回新 PoseResult（不原地改输入；保留原 ``valid_mask``）。"""
    kp, vis = refine_pose_keypoints(pose.keypoints, pose.visibility, fps=pose.fps)
    return PoseResult(
        keypoints=kp,
        visibility=vis,
        valid_mask=pose.valid_mask.copy(),
        num_frames=pose.num_frames,
        fps=pose.fps,
    )
