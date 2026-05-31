"""P2-M7-R1 · 真视频回归共享 helper（AC-A1 / AC-B1 / AC-B2）。"""

from __future__ import annotations

from pathlib import Path

from app.pipeline.camera_angle import infer_camera_angle_from_pose
from app.pipeline.features import extract_features
from app.pipeline.multi_swing import segment_phases_with_multi_swing
from app.pipeline.pose import estimate_poses
from app.pipeline.pose_denoise import denoise_pose_result
from app.pipeline.pose_refine import refine_pose_result
from app.pipeline.preprocess import preprocess_video
from app.pipeline.rotation_track import RotationTrackResult, apply_rotation_track


def shoulder_rotation_from_video(
    video_path: Path | str,
    *,
    declared_camera_angle: str | None = "face_on",
) -> tuple[float | None, list[str], RotationTrackResult | None]:
    """pose → phases → rotation_track，返回肩转读数与 quality_warnings。"""
    pre = preprocess_video(str(video_path))
    pose_result = refine_pose_result(denoise_pose_result(estimate_poses(pre.normalized_video_path)))
    phases, _, _ = segment_phases_with_multi_swing(pose_result)
    features = extract_features(pose_result.keypoints, phases)
    angle_result = infer_camera_angle_from_pose(
        pose_result,
        declared_raw=declared_camera_angle,
    )
    track_meta: list[RotationTrackResult] = []
    features = apply_rotation_track(
        features,
        pose_result.keypoints,
        phases,
        visibility=pose_result.visibility,
        camera_angle=angle_result.effective_angle,  # type: ignore[arg-type]
        track_result_out=track_meta,
    )
    track = track_meta[0] if track_meta else None
    shoulder = features.get("shoulder_rotation_top")
    if shoulder is None and track is not None:
        shoulder = track.shoulder_rotation_top
    warnings = list(track.quality_warnings) if track else []
    return shoulder, warnings, track


def coefficient_of_variation_percent(values: list[float]) -> float:
    """样本 CV（%）= 100 * stdev / mean；mean≈0 时返回 inf。"""
    if len(values) < 2:
        raise ValueError("CV 至少需要 2 个样本")
    mean = sum(values) / len(values)
    if abs(mean) < 1e-6:
        return float("inf")
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return 100.0 * (variance**0.5) / abs(mean)
