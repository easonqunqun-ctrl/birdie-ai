"""P2-M7-04 · 机位独立标尺：机位检测 + 偏角度量 + enum 规范化。

详 docs/release-notes/p2-m7-04-camera-angle-calibration-kickoff.md v0.1.1。

模块职责
--------
1. `normalize_camera_angle(raw)` — 三套命名（ECS manifest dtl / API down_the_line /
   docs/23 dtl）统一到 API 内部枚举（FR-1 配套）
2. `detect_camera_angle(pose_summary)` — 启发式机位识别（PoC 级，W18 标定）
3. `resolve_effective_angle(detected, declared, conf)` — §4.3 fallback 规则
4. `CameraAngleResult` dataclass — pipeline 出参

设计要点
--------
- 检测层 PoC 用关键点几何（左/右肩 x 距离 vs 头/髋 z 深度比）；W18 标定后改为
  小型 CNN（ECS angle 子集喂入）
- `oblique` **仅作中间态**：DB 入库前必经 fallback 转为 face_on / down_the_line
- offset_deg ∈ [0, 90]；>15° 触发 `analysis_confidence < 0.5`（与 M7-06 联动）

与 M7-06 关系
-------------
- 本模块输出 `offset_deg` → `compute_analysis_confidence(camera_angle_offset_deg=...)`
- M7-06 阈值常量 `ANGLE_HARD_OFFSET_DEG = 15.0` 与本文件 `OFFSET_HARD_THRESHOLD` 等价
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from app.pipeline.engine_warnings import EngineWarning

CameraAngleEnum = Literal["face_on", "down_the_line"]
DetectedAngleEnum = Literal["face_on", "down_the_line", "oblique"]

# ============================================================
# 阈值常量（kickoff §3.3）
# ============================================================

OFFSET_HARD_THRESHOLD = 15.0  # 与 M7-06 ANGLE_HARD_OFFSET_DEG 对齐
DETECTION_CONFIDENCE_FALLBACK = 0.7  # <0.7 退化到 declared_angle


# ============================================================
# 数据结构
# ============================================================


@dataclass(frozen=True)
class CameraAngleResult:
    """机位检测结果（pipeline 出参 + DB 入库前归一化）。"""

    detected_angle: DetectedAngleEnum
    offset_deg: float  # [0, 90]
    confidence: float  # 0-1
    declared_angle: CameraAngleEnum | None  # 用户声明（已 normalize）
    mismatch: bool  # detected != declared 且 confidence > 0.7

    @property
    def effective_angle(self) -> CameraAngleEnum:
        """选套规则（kickoff §3.2 v0.1.1）。"""
        return resolve_effective_angle(
            detected=self.detected_angle,
            declared=self.declared_angle,
            confidence=self.confidence,
        )

    @property
    def should_recommend_retake(self) -> bool:
        """offset > 15° → 强制建议重拍（kickoff §3.3）。"""
        return self.offset_deg > OFFSET_HARD_THRESHOLD


# ============================================================
# enum 规范化（kickoff §3.2.1）
# ============================================================


_FACE_ON_ALIASES: frozenset[str] = frozenset({"face_on", "face-on", "faceon"})
_DTL_ALIASES: frozenset[str] = frozenset(
    {"dtl", "down_the_line", "down-the-line", "downtheline", "DTL"}
)


def normalize_camera_angle(raw: str | None) -> CameraAngleEnum | None:
    """统一三套命名为 API 内部枚举。

    Returns:
        - face_on / down_the_line
        - None（输入为 None / 空字符串 / oblique 中间态）

    Raises:
        ValueError：输入不在已知映射表（防止 typo 进库）
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    low = s.lower()
    if low in _FACE_ON_ALIASES:
        return "face_on"
    if low in _DTL_ALIASES:
        return "down_the_line"
    if low == "oblique":
        return None
    raise ValueError(
        f"未知 camera_angle 别名：{raw!r}；合法值 face_on/down_the_line/dtl/oblique"
    )


# ============================================================
# 选套 fallback（kickoff §4.3）
# ============================================================


def resolve_effective_angle(
    *,
    detected: DetectedAngleEnum,
    declared: CameraAngleEnum | None,
    confidence: float,
) -> CameraAngleEnum:
    """选套规则：
    1. detected 是 face_on / down_the_line 且 confidence >= 0.7 → 用 detected
    2. detected 是 oblique 或 confidence < 0.7 → fallback 到 declared
    3. declared 也缺失 → 兜底 face_on（保守，后续 offset_deg 惩罚 confidence）
    """
    if detected in ("face_on", "down_the_line") and confidence >= DETECTION_CONFIDENCE_FALLBACK:
        return detected  # type: ignore[return-value]
    if declared is not None:
        return declared
    return "face_on"


# ============================================================
# 启发式检测（PoC v0.1，W18 ECS 标定后替换为 CNN）
# ============================================================


@dataclass(frozen=True)
class _PoseSummary:
    """从 PoseResult 抽取的几何摘要，供检测器使用。

    解耦原因：避免 camera_angle.py 直接依赖 numpy / PoseResult，便于纯 Python 单测。
    """

    left_shoulder_x: float
    right_shoulder_x: float
    left_hip_x: float
    right_hip_x: float
    head_x: float
    head_y: float
    valid_frame_ratio: float


def summarize_pose_for_angle(
    *,
    left_shoulder_x: float,
    right_shoulder_x: float,
    left_hip_x: float,
    right_hip_x: float,
    head_x: float,
    head_y: float,
    valid_frame_ratio: float = 1.0,
) -> _PoseSummary:
    """工厂函数：从外部输入（已聚合的关键点）构造 _PoseSummary。"""
    return _PoseSummary(
        left_shoulder_x=left_shoulder_x,
        right_shoulder_x=right_shoulder_x,
        left_hip_x=left_hip_x,
        right_hip_x=right_hip_x,
        head_x=head_x,
        head_y=head_y,
        valid_frame_ratio=valid_frame_ratio,
    )


def detect_camera_angle(summary: _PoseSummary) -> CameraAngleResult:
    """启发式机位检测 PoC。

    判定规则（v0.1，W18 ECS 标定后替换）：
    - 肩宽（|left_shoulder_x - right_shoulder_x|）大 → 正面 face_on
    - 肩宽小（侧身遮挡）→ down_the_line
    - 中间值 → oblique（中间态）

    offset_deg 估算：
    - face_on 标准：肩宽 ≈ 0.20-0.30（MediaPipe 归一化坐标）
    - dtl   标准：肩宽 ≈ 0.04-0.08
    - 偏离标准值按 cosine 拟合估算偏角（PoC，W18 标定）

    confidence：valid_frame_ratio × 肩宽稳定性近似
    """
    shoulder_width = abs(summary.left_shoulder_x - summary.right_shoulder_x)
    hip_width = abs(summary.left_hip_x - summary.right_hip_x)

    # PoC 阈值（W18 标定）
    FACE_ON_MIN_WIDTH = 0.18
    DTL_MAX_WIDTH = 0.09

    if shoulder_width >= FACE_ON_MIN_WIDTH:
        detected: DetectedAngleEnum = "face_on"
        # 偏角：以标准 face_on 肩宽 0.25 为基准，偏离按 cos 反演
        ideal = 0.25
        offset_cos = max(-1.0, min(1.0, shoulder_width / ideal))
        offset_deg = math.degrees(math.acos(offset_cos)) if offset_cos <= 1 else 0.0
    elif shoulder_width <= DTL_MAX_WIDTH:
        detected = "down_the_line"
        ideal = 0.06
        # dtl 时肩宽越大越偏角
        offset_deg = max(0.0, min(45.0, (shoulder_width - ideal) / ideal * 30.0))
    else:
        detected = "oblique"
        # 介于两者之间 → 估算到最近标准机位的偏角
        offset_to_face_on = abs(shoulder_width - 0.25) / 0.25 * 45.0
        offset_to_dtl = abs(shoulder_width - 0.06) / 0.06 * 30.0
        offset_deg = min(offset_to_face_on, offset_to_dtl)

    offset_deg = max(0.0, min(90.0, offset_deg))

    # confidence：valid_frame_ratio 加上 width/hip_width 一致性奖励
    width_consistency = 1.0 - min(
        1.0, abs(shoulder_width - hip_width) / max(shoulder_width, hip_width, 1e-6)
    )
    confidence = max(0.0, min(1.0, summary.valid_frame_ratio * (0.7 + 0.3 * width_consistency)))

    return CameraAngleResult(
        detected_angle=detected,
        offset_deg=offset_deg,
        confidence=confidence,
        declared_angle=None,  # 调用方 attach
        mismatch=False,
    )


def attach_declared(
    result: CameraAngleResult, declared_raw: str | None
) -> CameraAngleResult:
    """把用户声明 attach 到检测结果上 + 计算 mismatch。

    使用 frozen dataclass 的常见替换模式：返回新实例。
    """
    declared = normalize_camera_angle(declared_raw)
    mismatch = bool(
        declared is not None
        and result.detected_angle != declared
        and result.confidence >= DETECTION_CONFIDENCE_FALLBACK
        and result.detected_angle != "oblique"
    )
    return CameraAngleResult(
        detected_angle=result.detected_angle,
        offset_deg=result.offset_deg,
        confidence=result.confidence,
        declared_angle=declared,
        mismatch=mismatch,
    )


# ============================================================
# engine_warnings 生成（M7-02 联动）
# ============================================================


def angle_engine_warnings(result: CameraAngleResult) -> list[EngineWarning]:
    """根据检测结果生成 engine_warnings 条目。

    与 P2-M7-02 engine_warnings 框架对齐：
    - `camera_angle_large_offset`：>15° 偏角（kickoff §3.3 + AC-3）
    - `camera_angle_mismatch`：detected != declared（kickoff R-03）
    """
    warnings: list[EngineWarning] = []
    if result.offset_deg > OFFSET_HARD_THRESHOLD:
        warnings.append(
            EngineWarning(
                code="camera_angle_large_offset",
                level="warn",
                detail=(
                    f"offset_deg={result.offset_deg:.1f} > {OFFSET_HARD_THRESHOLD}; "
                    f"detected={result.detected_angle}"
                ),
            )
        )
    if result.mismatch:
        warnings.append(
            EngineWarning(
                code="camera_angle_mismatch",
                level="info",
                detail=(
                    f"detected={result.detected_angle} != declared={result.declared_angle}; "
                    f"conf={result.confidence:.2f}"
                ),
            )
        )
    return warnings
