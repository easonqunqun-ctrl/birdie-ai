"""P2-M7-R1 / M7-04-UI · 上传机位推断单测."""

from __future__ import annotations

from app.pipeline.camera_angle import (
    CameraAngleResult,
    suggested_camera_angle_for_upload,
    summarize_pose_for_angle,
    detect_camera_angle,
)


def test_suggested_camera_angle_high_conf_face_on() -> None:
    summary = summarize_pose_for_angle(
        left_shoulder_x=0.35,
        right_shoulder_x=0.65,
        left_hip_x=0.38,
        right_hip_x=0.62,
        head_x=0.5,
        head_y=0.3,
        valid_frame_ratio=1.0,
    )
    detected = detect_camera_angle(summary)
    assert detected.detected_angle == "face_on"
    assert suggested_camera_angle_for_upload(detected) == "face_on"


def test_suggested_camera_angle_low_conf_returns_none() -> None:
    result = CameraAngleResult(
        detected_angle="face_on",
        offset_deg=5.0,
        confidence=0.5,
        declared_angle=None,
        mismatch=False,
    )
    assert suggested_camera_angle_for_upload(result) is None


def test_suggested_camera_angle_oblique_returns_none() -> None:
    result = CameraAngleResult(
        detected_angle="oblique",
        offset_deg=20.0,
        confidence=0.9,
        declared_angle=None,
        mismatch=False,
    )
    assert suggested_camera_angle_for_upload(result) is None
