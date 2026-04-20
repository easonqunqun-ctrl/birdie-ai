"""W6-T1：MediaPipe Pose 姿态估计。

职责
----
- 吃预处理后的视频路径，逐帧用 MediaPipe Pose 检测 33 个关键点
- 输出 **numpy 数组** 而不是 MediaPipe 原生对象，方便后续 T2 的特征/分段模块
  不依赖 MediaPipe 类型
- 质量门：若有效帧占比 < 70% 或无任何帧检出 → 抛 `NoPersonError`

为什么 MediaPipe 而不是 MMPose / OpenPose
---------------------------------------
- MediaPipe 的 Pose 模型（Blaze Pose）CPU 10fps+ 实时推理，10s 视频 3-8s 搞定
- 单 pip 包 + 自带模型权重，无需额外下载，部署最简
- 33 点版本覆盖了挥杆分析需要的所有点（肩/肘/腕/髋/膝/踝 + 手指）
- 精度对 MVP 够用（docs/05 §2.2 已定，"MVP 首选 MediaPipe"）

MediaPipe API 版本说明
---------------------
- 本文件使用 **`mediapipe.solutions.pose.Pose`**（传统 API）而非新的
  `mediapipe.tasks.vision.PoseLandmarker`（Tasks API）
- 原因：Tasks API 要求手动下载 `.task` 模型文件并挂载到容器，复杂度更高；
  Solutions API pip 装完即用，MVP 期优先简单
- 版本锁定：`mediapipe>=0.10.9,<0.11`（0.10.x 系列 Solutions API 稳定；
  未来 0.11 可能移除 Solutions，那时再迁 Tasks API）

关键点编号参考（MediaPipe Pose 33 点）
-------------------------------------
- 0: nose
- 11-12: 左右肩 | 13-14: 左右肘 | 15-16: 左右腕
- 23-24: 左右髋 | 25-26: 左右膝 | 27-28: 左右踝
- 其它：面部细节点 + 手指关键点（W6-T2 主要用肩/肘/腕/髋/膝/踝 12 个点）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.errors import NoPersonError, PoseModelError

log = logging.getLogger("ai_engine.pose")

# MediaPipe Pose 输出固定 33 个关键点
NUM_LANDMARKS = 33

# 关键点索引常量（方便 T2 特征层引用）
LANDMARK_NOSE = 0
LANDMARK_LEFT_SHOULDER = 11
LANDMARK_RIGHT_SHOULDER = 12
LANDMARK_LEFT_ELBOW = 13
LANDMARK_RIGHT_ELBOW = 14
LANDMARK_LEFT_WRIST = 15
LANDMARK_RIGHT_WRIST = 16
LANDMARK_LEFT_HIP = 23
LANDMARK_RIGHT_HIP = 24
LANDMARK_LEFT_KNEE = 25
LANDMARK_RIGHT_KNEE = 26
LANDMARK_LEFT_ANKLE = 27
LANDMARK_RIGHT_ANKLE = 28

# 质量阈值
MIN_VALID_FRAME_RATIO = 0.7
MIN_PER_FRAME_CONFIDENCE = 0.5  # 单帧关键点平均可见度阈值，低于就算"无效帧"


# ============================================================
# 数据结构
# ============================================================


@dataclass
class PoseResult:
    """姿态估计输出。

    Attributes:
        keypoints: shape=(F, 33, 3)；`xyz` 均是 MediaPipe 的**归一化**坐标系：
                   x ∈ [0, 1]（图像宽），y ∈ [0, 1]（图像高，y 向下增长！），
                   z ≈ 以髋中心为原点的相对深度，单位与 x 同尺度但**不可直接米化**
        visibility: shape=(F, 33)；每个关键点的可见度 [0, 1]，越大越可信
        valid_mask: shape=(F,)；该帧是否通过"平均 visibility ≥ 阈值"检验
        num_frames / fps: 元信息
    """

    keypoints: np.ndarray  # (F, 33, 3) float32
    visibility: np.ndarray  # (F, 33) float32
    valid_mask: np.ndarray  # (F,) bool
    num_frames: int
    fps: float

    @property
    def valid_frame_ratio(self) -> float:
        return float(self.valid_mask.mean()) if self.num_frames > 0 else 0.0

    @property
    def mean_confidence(self) -> float:
        if self.valid_mask.sum() == 0:
            return 0.0
        return float(self.visibility[self.valid_mask].mean())


# ============================================================
# 主入口
# ============================================================


def estimate_poses(
    video_path: Path | str,
    *,
    model_complexity: int = 1,
    min_detection_confidence: float = 0.5,
    min_tracking_confidence: float = 0.5,
    min_valid_frame_ratio: float = MIN_VALID_FRAME_RATIO,
    min_per_frame_confidence: float = MIN_PER_FRAME_CONFIDENCE,
) -> PoseResult:
    """对视频逐帧做 MediaPipe Pose 推理。

    Args:
        video_path: 已经归一化（30fps / ≤720p）的视频路径
        model_complexity: 0=lite（最快）/ 1=full（默认，平衡）/ 2=heavy（精确但慢）
        min_detection_confidence: 首帧检测阈值；每一帧"重新检测"时用
        min_tracking_confidence: 跟踪帧阈值；首帧检测后续帧使用的追踪阈值
        min_valid_frame_ratio: 有效帧占比下限（低于 → `NoPersonError`）
        min_per_frame_confidence: 单帧被判为"有效"的 visibility 均值阈值

    Returns:
        `PoseResult`

    Raises:
        NoPersonError: 有效帧占比过低
        PoseModelError: MediaPipe 初始化失败 / 推理中异常
    """
    try:
        import cv2  # 延迟 import
        import mediapipe as mp
    except ImportError as exc:
        raise PoseModelError(
            f"mediapipe / opencv 未安装：{exc}",
            user_message="AI 引擎依赖缺失，请联系运维",
        ) from exc

    video_path = Path(video_path)
    if not video_path.exists():
        raise PoseModelError(f"视频文件不存在：{video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise PoseModelError(f"OpenCV 无法打开视频：{video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    # MediaPipe Pose 是**有状态**的（帧间跟踪），必须在同一个实例里顺序喂帧
    try:
        pose_ctx = mp.solutions.pose.Pose(
            static_image_mode=False,  # video mode；帧间跟踪加速
            model_complexity=model_complexity,
            smooth_landmarks=True,  # 轻度时域平滑，减少抖动
            enable_segmentation=False,  # 不需要分割掩膜，省算力
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
    except Exception as exc:  # pragma: no cover - 环境问题，测试难覆盖
        raise PoseModelError(f"MediaPipe Pose 初始化失败：{exc}") from exc

    keypoints_list: list[np.ndarray] = []
    visibility_list: list[np.ndarray] = []

    try:
        with pose_ctx as pose:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame is None or frame.size == 0:
                    # 读帧失败，补零保持帧数对齐（后续 valid_mask 会标记为无效）
                    keypoints_list.append(np.zeros((NUM_LANDMARKS, 3), dtype=np.float32))
                    visibility_list.append(np.zeros(NUM_LANDMARKS, dtype=np.float32))
                    continue

                # MediaPipe 要 RGB；OpenCV 默认 BGR
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb.flags.writeable = False  # MediaPipe 要求（性能优化）
                try:
                    result = pose.process(rgb)
                except Exception as exc:  # pragma: no cover - 推理异常极少
                    raise PoseModelError(f"MediaPipe 推理失败：{exc}") from exc

                if result.pose_landmarks is None:
                    # 这一帧没检测到人；填零 + visibility 全 0
                    keypoints_list.append(np.zeros((NUM_LANDMARKS, 3), dtype=np.float32))
                    visibility_list.append(np.zeros(NUM_LANDMARKS, dtype=np.float32))
                    continue

                landmarks = result.pose_landmarks.landmark
                kp = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32)
                vis = np.array([lm.visibility for lm in landmarks], dtype=np.float32)
                keypoints_list.append(kp)
                visibility_list.append(vis)
    finally:
        cap.release()

    if not keypoints_list:
        raise NoPersonError(
            "视频无任何可读帧",
            user_message="视频无法读取，请重新上传",
        )

    keypoints = np.stack(keypoints_list, axis=0)  # (F, 33, 3)
    visibility = np.stack(visibility_list, axis=0)  # (F, 33)

    # valid_mask：每帧的 visibility 平均值超过阈值
    per_frame_conf = visibility.mean(axis=1)  # (F,)
    valid_mask = per_frame_conf >= min_per_frame_confidence

    num_frames = keypoints.shape[0]
    valid_ratio = float(valid_mask.mean())

    log.info(
        "pose_done",
        extra={
            "num_frames": num_frames,
            "total_frames_hint": total_frames,
            "valid_ratio": round(valid_ratio, 3),
            "mean_confidence": round(float(per_frame_conf.mean()), 3),
            "fps": fps,
        },
    )

    if valid_ratio < min_valid_frame_ratio:
        raise NoPersonError(
            f"有效帧占比 {valid_ratio:.1%} < {min_valid_frame_ratio:.0%}",
            user_message="视频中未检测到完整人物，请确保全身入镜",
        )

    return PoseResult(
        keypoints=keypoints,
        visibility=visibility,
        valid_mask=valid_mask,
        num_frames=num_frames,
        fps=fps,
    )
