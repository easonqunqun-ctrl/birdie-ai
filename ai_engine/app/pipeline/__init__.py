"""W6 真实姿态分析 pipeline 模块。

当前已完成：
  - T1: `preprocess`（ffmpeg 转码 + 质量指标）+ `pose`（MediaPipe 33 点）

待实现（各自 T 开工时补 export）：
  - T2: phases / features / scoring / diagnose / recommend
  - T3: visualize
"""

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
    estimate_poses,
)
from app.pipeline.preprocess import (
    MAX_DURATION_SEC,
    MAX_FRAME_LOSS_RATIO,
    MIN_CLARITY_SCORE,
    MIN_DURATION_SEC,
    TARGET_FPS,
    TARGET_SHORT_SIDE,
    PreprocessResult,
    preprocess_video,
)

__all__ = [
    "LANDMARK_LEFT_ANKLE",
    "LANDMARK_LEFT_ELBOW",
    "LANDMARK_LEFT_HIP",
    "LANDMARK_LEFT_KNEE",
    "LANDMARK_LEFT_SHOULDER",
    "LANDMARK_LEFT_WRIST",
    "LANDMARK_NOSE",
    "LANDMARK_RIGHT_ANKLE",
    "LANDMARK_RIGHT_ELBOW",
    "LANDMARK_RIGHT_HIP",
    "LANDMARK_RIGHT_KNEE",
    "LANDMARK_RIGHT_SHOULDER",
    "LANDMARK_RIGHT_WRIST",
    "MAX_DURATION_SEC",
    "MAX_FRAME_LOSS_RATIO",
    "MIN_CLARITY_SCORE",
    "MIN_DURATION_SEC",
    "NUM_LANDMARKS",
    "PoseResult",
    "PreprocessResult",
    "TARGET_FPS",
    "TARGET_SHORT_SIDE",
    "estimate_poses",
    "preprocess_video",
]
