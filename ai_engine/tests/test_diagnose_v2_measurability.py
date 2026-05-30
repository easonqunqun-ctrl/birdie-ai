"""diagnose_v2 机位可测性过滤单测。"""

from __future__ import annotations

from app.pipeline.real_pipeline_v2 import diagnose_v2


def test_dtl_skips_under_rotation_when_shoulder_unmeasurable() -> None:
    """DTL 下 shoulder_rotation 不可测 → 不触发 under_rotation。"""
    features = {
        "shoulder_rotation_top": 11.8,
        "hip_rotation_top": 119.0,
        "x_factor": 0.0,
    }
    issues = diagnose_v2(features, phases=None, camera_angle="down_the_line")
    types = {i.type for i in issues}
    assert "under_rotation" not in types


def test_dtl_skips_early_extension_at_borderline_spine_delta() -> None:
    """DTL 下 spine_angle_impact_delta 边缘可测 → 不触发 early_extension。"""
    features = {
        "spine_angle_impact_delta": 16.0,
        "downswing_sequence": 2.0,
    }
    issues = diagnose_v2(features, phases=None, camera_angle="down_the_line")
    types = {i.type for i in issues}
    assert "early_extension" not in types


def test_face_on_still_diagnoses_under_rotation() -> None:
    features = {"shoulder_rotation_top": 60.0}
    issues = diagnose_v2(features, phases=None, camera_angle="face_on")
    types = {i.type for i in issues}
    assert "under_rotation" in types
