"""机位 × 特征「可测性」表 + 特征 sanity（P2 评分护城河 v0.2）。

问题背景
--------
MediaPipe 2D 关键点在不同机位下，**并非每个 docs/05 特征都有物理意义**。
例如 DTL 下「肩线 2D 夹角变化」无法反映真实转肩，却会被 hard-zero 打成上杆 0 分。

设计原则（对齐 docs/20 §四）
----------------------------
1. **可测才计分**：measurability < 阈值 → 该特征不参与阶段分（权重重归一化）。
2. **无可测特征 → 中性分**（50），禁止整阶段 0（除非 pose 完全失败）。
3. **阶段分下限**（15）：有可测特征时，避免 hard-zero 叠加把阶段打到 0。
4. **Sanity**：明显 landmark 跳变（如髋转 >90°）先剔除，再计分。
5. 表为 v0.2 工程保守值；ECS 真样本标定后逐步替换（ENG-04 / ECS）。

其它科学信号（当前与后续）
--------------------------
- **已用**：pose visibility、阶段帧窗口（confidence.py）、tempo/下杆顺序等时序特征。
- **后续可叠加**（不在本 PR）：probe 慢动作/HDR（engine_warnings）、club tracking、IMU。
"""

from __future__ import annotations

from typing import Literal

from app.pipeline.constants import FEATURES, PHASE_ORDER

CameraAngleEnum = Literal["face_on", "down_the_line"]

# 机位下该特征「2D pose 能否稳定反映挥杆语义」0–1。
# 默认 0.75：未单独登记的特征在 face_on 仍参与计分。
_DEFAULT_MEASURABILITY = 0.75

MEASURABILITY_BY_ANGLE: dict[str, dict[str, float]] = {
    "face_on": {
        "spine_angle_setup": 0.92,
        "knee_flexion_setup": 0.88,
        "shoulder_rotation_top": 0.93,
        "hip_rotation_top": 0.88,
        "x_factor": 0.85,
        "left_arm_straightness": 0.72,
        "top_wrist_position": 0.80,
        "downswing_sequence": 0.42,
        "wrist_release_angle": 0.78,
        "wrist_release_timing": 0.75,
        "spine_angle_impact_delta": 0.90,
        "head_lateral_shift": 0.88,
        "tempo_ratio": 0.82,
        "finish_height": 0.80,
        "finish_balance": 0.78,
    },
    "down_the_line": {
        # 2D 肩/髋「连线转角」在 DTL 下不能代表转体 → 不参与上杆旋转计分
        "shoulder_rotation_top": 0.12,
        "hip_rotation_top": 0.30,
        "x_factor": 0.08,
        # 转播/慢镜 DTL 下肩髋连线相对垂直的 2D 角常系统性偏高
        "spine_angle_setup": 0.35,
        "knee_flexion_setup": 0.50,
        # 沿视线方向的直臂在 2D 肘角会严重偏小（典型职业片误报 chicken_wing）
        "left_arm_straightness": 0.28,
        "top_wrist_position": 0.88,
        "downswing_sequence": 0.92,
        "wrist_release_angle": 0.70,
        "wrist_release_timing": 0.68,
        # 击球脊柱变化在 DTL 可部分参考；诊断阈值另收紧（见 diagnose_v2）
        "spine_angle_impact_delta": 0.45,
        "head_lateral_shift": 0.35,
        "tempo_ratio": 0.80,
        "finish_height": 0.65,
        "finish_balance": 0.60,
    },
}

MIN_MEASURABILITY_TO_SCORE = 0.40
# 诊断比计分更严：避免 DTL 边缘可测特征误触发 issue
MIN_MEASURABILITY_TO_DIAGNOSE = 0.50
PHASE_SCORE_FLOOR = 15
PHASE_NEUTRAL_SCORE = 50

# quality_warnings machine codes
WARN_ANGLE_LIMITED_SCORING = "angle_limited_scoring"
WARN_ROTATION_SANITY = "rotation_reading_unreliable"


def measurability(feature_name: str, camera_angle: CameraAngleEnum | None) -> float:
    """未传机位（V1 计分路径）→ 1.0，保持历史行为。"""
    if camera_angle is None:
        return 1.0
    table = MEASURABILITY_BY_ANGLE.get(camera_angle, {})
    return table.get(feature_name, _DEFAULT_MEASURABILITY)


def sanitize_features(
    features: dict[str, float],
    *,
    camera_angle: CameraAngleEnum | None,
) -> tuple[dict[str, float], list[str]]:
    """剔除明显不合理的特征读数，返回 (新 dict, quality_warning codes)。"""
    out = dict(features)
    warnings: list[str] = []

    rotation_keys = ("shoulder_rotation_top", "hip_rotation_top", "x_factor")

    def _drop_rotation() -> None:
        for k in rotation_keys:
            out.pop(k, None)
        if WARN_ROTATION_SANITY not in warnings:
            warnings.append(WARN_ROTATION_SANITY)

    # P2-M7-R1 · 全局旋转 sanity（不限机位）
    shoulder = out.get("shoulder_rotation_top")
    if shoulder is not None and (
        shoulder < 15.0 or shoulder > 110.0
    ):
        _drop_rotation()
        shoulder = out.get("shoulder_rotation_top")

    xf = out.get("x_factor")
    if xf is not None and xf > 80.0:
        _drop_rotation()

    # DTL：旋转类 2D 不可信，一律不参与计分/诊断
    if camera_angle == "down_the_line":
        if any(k in out for k in rotation_keys):
            _drop_rotation()

    hip = out.get("hip_rotation_top")
    if hip is not None and hip > 90.0:
        out.pop("hip_rotation_top", None)
        out.pop("x_factor", None)
        warnings.append(WARN_ROTATION_SANITY)

    shoulder = out.get("shoulder_rotation_top")
    if (
        camera_angle == "down_the_line"
        and shoulder is not None
        and shoulder < 25.0
        and hip is not None
        and hip > 70.0
    ):
        # 肩读数极低 + 髋读数极高 → 典型 DTL 投影/遮挡矛盾，旋转类不可信
        out.pop("shoulder_rotation_top", None)
        out.pop("hip_rotation_top", None)
        out.pop("x_factor", None)
        if WARN_ROTATION_SANITY not in warnings:
            warnings.append(WARN_ROTATION_SANITY)

    if camera_angle == "down_the_line" and "x_factor" in out:
        xf = out["x_factor"]
        if xf <= 0.0 and shoulder is not None and shoulder < 30.0:
            out.pop("x_factor", None)

    if camera_angle == "down_the_line":
        shoulder = out.get("shoulder_rotation_top")
        if shoulder is not None and shoulder > 100.0:
            # DTL 肩线 2D 角 >100° 为转播/慢镜投影失真，非真实转肩
            out.pop("shoulder_rotation_top", None)
            out.pop("x_factor", None)
            if WARN_ROTATION_SANITY not in warnings:
                warnings.append(WARN_ROTATION_SANITY)

        wrist = out.get("top_wrist_position")
        if wrist is not None and wrist < 0.08:
            # 顶点手腕低于头/不可见：DTL 转播常见，连带左臂 2D 肘角不可信
            out.pop("top_wrist_position", None)
            out.pop("left_arm_straightness", None)

        arm = out.get("left_arm_straightness")
        wrist = out.get("top_wrist_position")
        if (
            arm is not None
            and arm < 130.0
            and wrist is not None
            and 0.08 <= wrist <= 0.45
        ):
            out.pop("left_arm_straightness", None)

        tempo = out.get("tempo_ratio")
        if tempo is not None and (tempo > 5.5 or tempo < 1.2):
            # 阶段切分在慢镜/转播上常失真，节奏比不可信
            out.pop("tempo_ratio", None)

        spine_setup = out.get("spine_angle_setup")
        if spine_setup is not None and spine_setup > 40.0:
            out.pop("spine_angle_setup", None)

    return out, warnings


def issue_measurability(issue_feature_names: list[str], camera_angle: CameraAngleEnum | None) -> float:
    """诊断 rule 关联特征的最低可测性（短板）。"""
    if not issue_feature_names:
        return 1.0
    return min(measurability(n, camera_angle) for n in issue_feature_names)


def scoring_quality_warnings(
    camera_angle: CameraAngleEnum | None,
    skipped_features: set[str],
) -> list[str]:
    if not camera_angle or not skipped_features:
        return []
    rotation_skipped = skipped_features & {
        "shoulder_rotation_top",
        "hip_rotation_top",
        "x_factor",
    }
    if rotation_skipped and camera_angle == "down_the_line":
        return [WARN_ANGLE_LIMITED_SCORING]
    if len(skipped_features) >= 3:
        return [WARN_ANGLE_LIMITED_SCORING]
    return []


def all_feature_names() -> list[str]:
    return [f["name"] for f in FEATURES]


def phase_has_scorable_features(
    features: dict[str, float],
    phase: str,
    *,
    camera_angle: CameraAngleEnum | None,
    feature_confidences: dict[str, float] | None = None,
    min_confidence: float | None = None,
) -> bool:
    """该阶段是否至少有一个特征会参与计分（供 overall 权重重归一化）。"""
    from app.pipeline.constants import FEATURES_BY_PHASE

    if min_confidence is None:
        from app.pipeline.score_trust import MIN_FEATURE_CONFIDENCE_TO_SCORE

        min_confidence = MIN_FEATURE_CONFIDENCE_TO_SCORE

    for meta in FEATURES_BY_PHASE.get(phase, []):
        name = meta["name"]
        if name not in features:
            continue
        if measurability(name, camera_angle) < MIN_MEASURABILITY_TO_SCORE:
            continue
        if feature_confidences is not None:
            if feature_confidences.get(name, 0.0) < min_confidence:
                continue
        return True
    return False


def phases_with_measurable_features(camera_angle: CameraAngleEnum | None) -> set[str]:
    """返回至少有一个可测特征的 phase keys。"""
    from app.pipeline.constants import FEATURES_BY_PHASE

    out: set[str] = set()
    for phase in PHASE_ORDER:
        for meta in FEATURES_BY_PHASE.get(phase, []):
            if measurability(meta["name"], camera_angle) >= MIN_MEASURABILITY_TO_SCORE:
                out.add(phase)
                break
    return out
