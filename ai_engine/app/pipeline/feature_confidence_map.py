"""计分前：按特征窗口从 pose.visibility 预估各特征可信度。"""

from __future__ import annotations

from app.pipeline.confidence import feature_confidence
from app.pipeline.phases import PhaseSegmentResult
from app.pipeline.pose import PoseResult


def compute_feature_confidences(
    pose: PoseResult,
    phases: PhaseSegmentResult,
) -> dict[str, float]:
    """Layer-1 特征 confidence；供计分过滤与 trust 校准复用。"""
    from app.pipeline.real_pipeline_v2 import _visibility_sub_for_feature

    out: dict[str, float] = {}
    for name in (
        "spine_angle_setup",
        "knee_flexion_setup",
        "shoulder_rotation_top",
        "hip_rotation_top",
        "x_factor",
        "left_arm_straightness",
        "top_wrist_position",
        "downswing_sequence",
        "wrist_release_angle",
        "wrist_release_timing",
        "spine_angle_impact_delta",
        "head_lateral_shift",
        "tempo_ratio",
        "finish_height",
        "finish_balance",
    ):
        sub = _visibility_sub_for_feature(pose, phases, name)
        out[name] = round(float(feature_confidence(sub)), 3)
    return out
