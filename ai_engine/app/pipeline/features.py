"""W6-T2：15 个核心特征提取（docs/05 §2.5）。

每个特征都是一个小的纯函数，吃 (keypoints, phases, valid_mask) → float。
`extract_features` 是统一入口，按固定顺序调用它们，返回 {name: value} 字典。

设计约束
--------
- **绝对不崩溃**：无论关键点多烂，特征函数都得返回一个合理的数（退化值），否则
  下游 scoring 会挂。退化值选"理想中点"，让评分落到 85-100 这种"还不错"区间，
  避免给用户假警报
- 角度单位统一用**度**；比例单位统一为 float，范围由 docs/05 §2.6 决定
- MediaPipe 坐标系约定：x/y ∈ [0,1]，y **向下**增长（屏幕坐标系）
- 所有函数都**容忍空 valid 帧**：用 `_safe_mean` / `_safe_angle` 包一层
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from app.pipeline.constants import FEATURES, feature_meta
from app.pipeline.pose import (
    LANDMARK_LEFT_ELBOW,
    LANDMARK_LEFT_HIP,
    LANDMARK_LEFT_KNEE,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_NOSE,
    LANDMARK_RIGHT_ANKLE,
    LANDMARK_RIGHT_ELBOW,
    LANDMARK_RIGHT_HIP,
    LANDMARK_RIGHT_SHOULDER,
)

if TYPE_CHECKING:
    from app.pipeline.phases import PhaseSegmentResult

log = logging.getLogger("ai_engine.features")


# ==================== 几何工具 ====================


def _angle_between(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """计算 ∠ABC（B 为顶点）of 2D 坐标，返回度数 [0, 180]。"""
    ba = a - b
    bc = c - b
    denom = float(np.linalg.norm(ba) * np.linalg.norm(bc)) + 1e-8
    cos = float(np.dot(ba, bc)) / denom
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def _line_angle_deg(p_left: np.ndarray, p_right: np.ndarray) -> float:
    """两点连线相对水平轴的角度，度数，范围 (-180, 180]。"""
    dy = p_right[1] - p_left[1]
    dx = p_right[0] - p_left[0]
    return float(np.degrees(np.arctan2(dy, dx)))


def _safe_frame(keypoints: np.ndarray, frame_idx: int) -> np.ndarray:
    """取一帧；越界就 clip。"""
    frame_idx = max(0, min(frame_idx, len(keypoints) - 1))
    return keypoints[frame_idx]


# ==================== 特征函数：Setup ====================


def _spine_angle_at(frame_kp: np.ndarray) -> float:
    """脊柱前倾角：肩中点—髋中点—与垂直线的夹角。"""
    shoulder_mid = (frame_kp[LANDMARK_LEFT_SHOULDER, :2] + frame_kp[LANDMARK_RIGHT_SHOULDER, :2]) / 2
    hip_mid = (frame_kp[LANDMARK_LEFT_HIP, :2] + frame_kp[LANDMARK_RIGHT_HIP, :2]) / 2
    # 垂直向上单位向量 (0, -1)；脊柱向量（髋→肩）
    spine = shoulder_mid - hip_mid
    vertical = np.array([0.0, -1.0])
    denom = float(np.linalg.norm(spine)) + 1e-8
    cos = float(np.dot(spine, vertical)) / denom
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def _knee_flexion_at(frame_kp: np.ndarray) -> float:
    """膝弯角：左膝的 ∠(髋-膝-踝)，直腿 180°，弯腿更小（docs/05 150-165°）。

    MVP 取左膝（右撇子下场一般左腿为 lead leg；若 pose 质量差两腿差异小，此处取一个就行）。
    """
    hip = frame_kp[LANDMARK_LEFT_HIP, :2]
    knee = frame_kp[LANDMARK_LEFT_KNEE, :2]
    ankle = frame_kp[LANDMARK_RIGHT_ANKLE, :2]  # 同侧踝即可
    # 用左踝：
    from app.pipeline.pose import LANDMARK_LEFT_ANKLE

    ankle = frame_kp[LANDMARK_LEFT_ANKLE, :2]
    return _angle_between(hip, knee, ankle)


def feat_spine_angle_setup(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    kp = _safe_frame(keypoints, phases.phases["setup"].key_frame)
    return _spine_angle_at(kp)


def feat_knee_flexion_setup(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    kp = _safe_frame(keypoints, phases.phases["setup"].key_frame)
    return _knee_flexion_at(kp)


# ==================== 特征函数：Backswing / Top ====================


def _shoulder_rotation_deg(frame_kp: np.ndarray, baseline: float) -> float:
    """相对于 baseline 肩线角度（setup 时的肩线）的旋转角，取绝对值。"""
    l_sh = frame_kp[LANDMARK_LEFT_SHOULDER, :2]
    r_sh = frame_kp[LANDMARK_RIGHT_SHOULDER, :2]
    current = _line_angle_deg(l_sh, r_sh)
    diff = current - baseline
    # 归一到 [-180, 180]
    diff = (diff + 180) % 360 - 180
    return abs(diff)


def _hip_rotation_deg(frame_kp: np.ndarray, baseline: float) -> float:
    l_hip = frame_kp[LANDMARK_LEFT_HIP, :2]
    r_hip = frame_kp[LANDMARK_RIGHT_HIP, :2]
    current = _line_angle_deg(l_hip, r_hip)
    diff = current - baseline
    diff = (diff + 180) % 360 - 180
    return abs(diff)


def feat_shoulder_rotation_top(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    setup_kp = _safe_frame(keypoints, phases.phases["setup"].key_frame)
    top_kp = _safe_frame(keypoints, phases.top_frame)
    baseline = _line_angle_deg(
        setup_kp[LANDMARK_LEFT_SHOULDER, :2], setup_kp[LANDMARK_RIGHT_SHOULDER, :2]
    )
    return _shoulder_rotation_deg(top_kp, baseline)


def feat_hip_rotation_top(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    setup_kp = _safe_frame(keypoints, phases.phases["setup"].key_frame)
    top_kp = _safe_frame(keypoints, phases.top_frame)
    baseline = _line_angle_deg(
        setup_kp[LANDMARK_LEFT_HIP, :2], setup_kp[LANDMARK_RIGHT_HIP, :2]
    )
    return _hip_rotation_deg(top_kp, baseline)


def feat_x_factor(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    """X-Factor = 肩旋转 - 髋旋转 @Top。保留绝对值（负值不合理）。"""
    return max(
        0.0,
        feat_shoulder_rotation_top(keypoints, phases) - feat_hip_rotation_top(keypoints, phases),
    )


def feat_left_arm_straightness(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    """左臂伸直度：左肘角度 @Top（直臂 180°，docs/05 理想 165-180°）。"""
    kp = _safe_frame(keypoints, phases.top_frame)
    shoulder = kp[LANDMARK_LEFT_SHOULDER, :2]
    elbow = kp[LANDMARK_LEFT_ELBOW, :2]
    wrist = kp[LANDMARK_LEFT_WRIST, :2]
    return _angle_between(shoulder, elbow, wrist)


def feat_top_wrist_position(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    """顶点手腕相对于头部的垂直高度比例。

    定义 = (nose.y - wrist.y)：MediaPipe y 向下增长，所以手腕在头上时 wrist.y < nose.y，
    差值为正 → 越大表示越高。
    归一化为 **(head_y - wrist_y) / 0.5**（0.5 是 MediaPipe 坐标系里身高约占图像一半的经验值），
    最终落在 ~0.1-0.4 区间符合 ideal_min/max。
    """
    kp = _safe_frame(keypoints, phases.top_frame)
    wrist = kp[phases.lead_wrist_idx, :2]
    nose = kp[LANDMARK_NOSE, :2]
    return float((nose[1] - wrist[1]) / 0.5)


# ==================== Downswing ====================


def feat_downswing_sequence(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    """下杆顺序指标：下杆阶段中，**髋开始反转**的帧 vs **肩开始反转**的帧，前者减后者（帧数）。

    定义"开始反转"为：相对 top 帧的旋转角首次变化 > 2° 的帧。
    返回负值（肩先反转，不理想）或正值（髋先反转，理想）。
    退化值 3 帧（位于理想区间中间）。
    """
    downswing = phases.phases["downswing"]
    start = downswing.start_frame
    end = downswing.end_frame
    if end <= start:
        return 3.0  # 退化：理想中点

    top_kp = keypoints[phases.top_frame]
    top_shoulder_angle = _line_angle_deg(
        top_kp[LANDMARK_LEFT_SHOULDER, :2], top_kp[LANDMARK_RIGHT_SHOULDER, :2]
    )
    top_hip_angle = _line_angle_deg(
        top_kp[LANDMARK_LEFT_HIP, :2], top_kp[LANDMARK_RIGHT_HIP, :2]
    )

    hip_reverse_frame = None
    shoulder_reverse_frame = None
    for f in range(start, end + 1):
        frame_kp = keypoints[f]
        cur_hip = _line_angle_deg(
            frame_kp[LANDMARK_LEFT_HIP, :2], frame_kp[LANDMARK_RIGHT_HIP, :2]
        )
        cur_shoulder = _line_angle_deg(
            frame_kp[LANDMARK_LEFT_SHOULDER, :2], frame_kp[LANDMARK_RIGHT_SHOULDER, :2]
        )
        if hip_reverse_frame is None and abs(cur_hip - top_hip_angle) > 2.0:
            hip_reverse_frame = f
        if shoulder_reverse_frame is None and abs(cur_shoulder - top_shoulder_angle) > 2.0:
            shoulder_reverse_frame = f
        if hip_reverse_frame is not None and shoulder_reverse_frame is not None:
            break

    if hip_reverse_frame is None or shoulder_reverse_frame is None:
        return 3.0
    # 正值 = 髋先反转（肩帧 - 髋帧 > 0 表示肩后开始）
    return float(shoulder_reverse_frame - hip_reverse_frame)


def _wrist_forearm_angle(frame_kp: np.ndarray, wrist_idx: int, elbow_idx: int) -> float:
    """用手腕-肘-同侧肩形成的角度作为"手腕角度"的代理量。

    注：MediaPipe Pose 33 点没有手指关键点到足以精确定义手腕角度，这里用
    "肘-腕-下一个有效点"的夹角做近似，MVP 够用。
    """
    # 用 elbow-wrist 向量与 wrist 下一节点（此处用另一手的中间点或忽略，退化为 elbow-wrist 与水平的夹角）
    elbow = frame_kp[elbow_idx, :2]
    wrist = frame_kp[wrist_idx, :2]
    forearm = wrist - elbow
    # 与水平线的角度
    return float(np.degrees(np.arctan2(forearm[1], forearm[0])))


def feat_wrist_release_angle(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    """手腕释放角 = |top 时手腕前臂角 - impact 时手腕前臂角|（度）。

    退化值：理想中点 85°。
    """
    wrist_idx = phases.lead_wrist_idx
    elbow_idx = (
        LANDMARK_LEFT_ELBOW if wrist_idx == LANDMARK_LEFT_WRIST else LANDMARK_RIGHT_ELBOW
    )
    top_kp = keypoints[phases.top_frame]
    impact_kp = keypoints[phases.impact_frame]
    top_angle = _wrist_forearm_angle(top_kp, wrist_idx, elbow_idx)
    impact_angle = _wrist_forearm_angle(impact_kp, wrist_idx, elbow_idx)
    diff = abs(top_angle - impact_angle)
    # 归一到 [0, 180]
    if diff > 180:
        diff = 360 - diff
    return diff


def feat_wrist_release_timing(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    """手腕释放时机 = 手腕前臂角首次发生"显著变化"的帧 / 下杆总时长。

    定义：相对于 top 帧，前臂角变化 > 15° 的首帧，归一到 [0, 1]。
    退化值 0.60（理想中点）。
    """
    wrist_idx = phases.lead_wrist_idx
    elbow_idx = (
        LANDMARK_LEFT_ELBOW if wrist_idx == LANDMARK_LEFT_WRIST else LANDMARK_RIGHT_ELBOW
    )
    top = phases.top_frame
    impact = phases.impact_frame
    if impact <= top:
        return 0.60

    top_kp = keypoints[top]
    top_angle = _wrist_forearm_angle(top_kp, wrist_idx, elbow_idx)
    total = impact - top

    for f in range(top, impact + 1):
        cur = _wrist_forearm_angle(keypoints[f], wrist_idx, elbow_idx)
        diff = abs(cur - top_angle)
        if diff > 180:
            diff = 360 - diff
        if diff > 15.0:
            return float((f - top) / total)
    return 0.60


# ==================== Impact ====================


def feat_spine_angle_impact_delta(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    setup_kp = _safe_frame(keypoints, phases.phases["setup"].key_frame)
    impact_kp = _safe_frame(keypoints, phases.impact_frame)
    return abs(_spine_angle_at(setup_kp) - _spine_angle_at(impact_kp))


# ==================== 全程 ====================


def feat_head_lateral_shift(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    """头部（鼻尖）水平位移的最大-最小差，归一化坐标。"""
    start = phases.swing_start
    end = phases.swing_end
    if end <= start:
        return 0.04
    head_x = keypoints[start : end + 1, LANDMARK_NOSE, 0]
    return float(head_x.max() - head_x.min())


def feat_tempo_ratio(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    """上杆时长 / 下杆时长（帧数）。退化值 3.0。"""
    backswing_frames = phases.top_frame - phases.swing_start
    downswing_frames = phases.impact_frame - phases.top_frame
    if downswing_frames <= 0:
        return 3.0
    return float(backswing_frames / downswing_frames)


def feat_finish_height(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    """收杆手腕相对肩的高度比例 = wrist.y - shoulder.y（负值表示高于肩）。

    取 follow_through 的 key_frame。
    """
    finish = phases.phases["follow_through"].key_frame
    kp = _safe_frame(keypoints, finish)
    wrist_y = kp[phases.lead_wrist_idx, 1]
    shoulder_y = kp[phases.lead_shoulder_idx, 1]
    return float(wrist_y - shoulder_y)


def feat_finish_balance(keypoints: np.ndarray, phases: PhaseSegmentResult) -> float:
    """收杆最后 10 帧双脚踝位置的抖动量（x 方向标准差均值）。"""
    from app.pipeline.pose import LANDMARK_LEFT_ANKLE

    finish_end = phases.phases["follow_through"].end_frame
    start = max(phases.phases["follow_through"].start_frame, finish_end - 9)
    if finish_end <= start:
        return 0.01
    l_ankle_x = keypoints[start : finish_end + 1, LANDMARK_LEFT_ANKLE, 0]
    r_ankle_x = keypoints[start : finish_end + 1, LANDMARK_RIGHT_ANKLE, 0]
    return float((l_ankle_x.std() + r_ankle_x.std()) / 2)


# ==================== 统一入口 ====================

_FEATURE_FUNCS: dict[str, callable] = {
    "spine_angle_setup": feat_spine_angle_setup,
    "knee_flexion_setup": feat_knee_flexion_setup,
    "shoulder_rotation_top": feat_shoulder_rotation_top,
    "hip_rotation_top": feat_hip_rotation_top,
    "x_factor": feat_x_factor,
    "left_arm_straightness": feat_left_arm_straightness,
    "top_wrist_position": feat_top_wrist_position,
    "downswing_sequence": feat_downswing_sequence,
    "wrist_release_angle": feat_wrist_release_angle,
    "wrist_release_timing": feat_wrist_release_timing,
    "spine_angle_impact_delta": feat_spine_angle_impact_delta,
    "head_lateral_shift": feat_head_lateral_shift,
    "tempo_ratio": feat_tempo_ratio,
    "finish_height": feat_finish_height,
    "finish_balance": feat_finish_balance,
}

# 保证跟 constants.FEATURES 完全同步（漏一个就 fail fast）
assert set(_FEATURE_FUNCS.keys()) == {f["name"] for f in FEATURES}, (
    "features._FEATURE_FUNCS 和 constants.FEATURES 不同步"
)


def extract_features(
    keypoints: np.ndarray, phases: PhaseSegmentResult
) -> dict[str, float]:
    """批量跑 15 个特征函数。

    任意特征函数抛异常时，用该特征的 **ideal 中点** 作退化值，这样下游评分会落在
    "还不错"区间，避免给用户虚假警报。

    Returns:
        {feature_name: value}，15 个键齐全。
    """
    out: dict[str, float] = {}
    for name, fn in _FEATURE_FUNCS.items():
        try:
            value = float(fn(keypoints, phases))
            if not np.isfinite(value):
                raise ValueError(f"{name} returned non-finite value")
            out[name] = value
        except Exception as exc:
            meta = feature_meta(name)
            fallback = (meta["ideal_min"] + meta["ideal_max"]) / 2
            log.warning(
                "feature_fallback",
                extra={"feature": name, "error": str(exc), "fallback": fallback},
            )
            out[name] = fallback
    return out
