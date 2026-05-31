"""P2-M7-R1 · AC-B1 真视频重复性回归（manifest R1 包）。

同一球友连拍 ≥2 段 face-on：``shoulder_rotation_top`` 帧间 CV < 15%。
fixture 未齐时 pytest skip，不阻塞 CI。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.conftest import REAL_DIR, resolve_manifest_fixture_video
from tests.rotation_regression_helpers import (
    coefficient_of_variation_percent,
    shoulder_rotation_from_video,
)

_mediapipe = pytest.importorskip("mediapipe", reason="mediapipe 未安装")
_cv2 = pytest.importorskip("cv2", reason="cv2 未安装")

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg 未安装",
)

_MANIFEST = Path(__file__).parent / "fixtures" / "rotation_regression_manifest.json"


def _repeatability_pack() -> dict:
    if not _MANIFEST.is_file():
        return {}
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    return manifest.get("packs", {}).get("R1_face_on_repeatability", {})


def _group_cases() -> list[dict]:
    pack = _repeatability_pack()
    return list(pack.get("groups") or [])


def _resolve_group_videos(group: dict) -> list[Path] | None:
    """每组需 ≥2 个可读 fixture；不足则返回 None（skip）。"""
    paths: list[Path] = []
    for case in group.get("cases") or []:
        video = resolve_manifest_fixture_video(case, real_dir=REAL_DIR)
        if video is not None:
            paths.append(video)
    min_swings = int(group.get("min_swings") or 2)
    if len(paths) < min_swings:
        return None
    return paths


def test_ac_b1_cv_helper_stable_triplet() -> None:
    from tests.rotation_regression_helpers import coefficient_of_variation_percent

    cv = coefficient_of_variation_percent([48.0, 50.0, 52.0])
    assert cv < 15.0


@needs_ffmpeg
@pytest.mark.parametrize("group", _group_cases(), ids=lambda g: g.get("id", "group"))
def test_ac_b1_face_on_repeatability_cv(group: dict) -> None:
    """AC-B1 · 同组连拍 shoulder_rotation_top CV < max_cv_percent。"""
    pack = _repeatability_pack()
    max_cv = float(pack.get("max_cv_percent") or 15.0)
    videos = _resolve_group_videos(group)
    if videos is None:
        pytest.skip(
            f"组 {group.get('id')} 缺 fixture（需 ≥{group.get('min_swings', 2)} 段）；"
            "见 fixtures/README.md · R1 包",
        )

    declared = group.get("declared_camera_angle") or group.get("camera_angle") or "face_on"
    readings: list[float] = []
    for video in videos:
        shoulder, warnings, track = shoulder_rotation_from_video(
            video,
            declared_camera_angle=declared,
        )
        if shoulder is not None:
            readings.append(float(shoulder))
            continue
        if track is not None and track.rotation_confidence <= 0.0:
            pytest.skip(
                f"{video.name}: rotation unreliable ({warnings or 'no reading'})",
            )

    if len(readings) < 2:
        pytest.skip(f"组 {group.get('id')} 有效读数 <2（{len(readings)}/{len(videos)}）")

    cv = coefficient_of_variation_percent(readings)
    assert cv < max_cv, (
        f"group={group.get('id')} readings={readings} CV={cv:.1f}% >= {max_cv}%"
    )
