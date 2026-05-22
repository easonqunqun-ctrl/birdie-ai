"""O-07：骨骼叠加输出 FPS 解析与门禁单测。"""

from __future__ import annotations

import pytest

from app.pipeline.visualize import (
    DEFAULT_SKELETON_OUTPUT_FPS,
    MIN_SKELETON_PLAYBACK_FPS,
    VideoStreamProbe,
    parse_ffprobe_fps,
    resolve_skeleton_output_fps,
    skeleton_playback_fps_ok,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("30/1", 30.0),
        ("30000/1001", pytest.approx(29.97, rel=1e-3)),
        ("0/0", 0.0),
        ("", 0.0),
        ("24", 24.0),
    ],
)
def test_parse_ffprobe_fps(raw: str, expected: float) -> None:
    assert parse_ffprobe_fps(raw) == expected


def test_resolve_skeleton_output_fps_defaults_to_30() -> None:
    assert resolve_skeleton_output_fps(container_fps=None, pose_fps=None) == DEFAULT_SKELETON_OUTPUT_FPS


def test_resolve_skeleton_output_fps_raises_floor_to_24() -> None:
    assert resolve_skeleton_output_fps(container_fps=15.0, pose_fps=None) == MIN_SKELETON_PLAYBACK_FPS


def test_resolve_skeleton_output_fps_aligns_near_30() -> None:
    assert resolve_skeleton_output_fps(container_fps=29.97, pose_fps=30.0) == DEFAULT_SKELETON_OUTPUT_FPS


def test_skeleton_playback_fps_ok() -> None:
    assert skeleton_playback_fps_ok(VideoStreamProbe(fps=30.0, frame_count=90, codec="h264"))
    assert skeleton_playback_fps_ok(VideoStreamProbe(fps=24.0, frame_count=72, codec="h264"))
    assert not skeleton_playback_fps_ok(VideoStreamProbe(fps=20.0, frame_count=60, codec="h264"))
    assert not skeleton_playback_fps_ok(None)
