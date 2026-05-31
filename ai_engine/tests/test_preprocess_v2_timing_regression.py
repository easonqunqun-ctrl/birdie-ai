"""P2-M7-R1-B7 · preprocess V1 vs V2 阶段时刻对齐回归（开 flag 前门禁）。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.pipeline.phases import PhaseSegmentResult
from tests.conftest import REAL_DIR, resolve_manifest_fixture_video
from tests.test_diagnose import _fake_phases
from tests.timing_regression_helpers import (
    DEFAULT_MAX_PHASE_DELTA_SEC,
    phase_key_times_sec,
    phase_timing_deltas_sec,
)

_mediapipe = pytest.importorskip("mediapipe", reason="mediapipe 未安装")
_cv2 = pytest.importorskip("cv2", reason="cv2 未安装")

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg 未安装",
)

_MANIFEST = Path(__file__).parent / "fixtures" / "rotation_regression_manifest.json"


def _timing_pack() -> dict:
    if not _MANIFEST.is_file():
        return {}
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    return manifest.get("packs", {}).get("R3_preprocess_v2_timing", {})


def _timing_cases() -> list[dict]:
    pack = _timing_pack()
    return [c for c in pack.get("cases", []) if c.get("source") == "fixture"]


def test_phase_timing_helper_identical_seconds() -> None:
    """合成：30fps@frame30 与 60fps@frame60 同一时刻 → Δt=0。"""
    phases_a = _fake_phases(30.0)
    phases_b = _fake_phases(60.0)
    phases_a = PhaseSegmentResult(
        phases=phases_a.phases,
        swing_start=10,
        swing_end=50,
        top_frame=30,
        impact_frame=36,
        handedness=phases_a.handedness,
        lead_wrist_idx=phases_a.lead_wrist_idx,
        lead_shoulder_idx=phases_a.lead_shoulder_idx,
        fps=30.0,
    )
    phases_b = PhaseSegmentResult(
        phases=phases_b.phases,
        swing_start=20,
        swing_end=100,
        top_frame=60,
        impact_frame=72,
        handedness=phases_b.handedness,
        lead_wrist_idx=phases_b.lead_wrist_idx,
        lead_shoulder_idx=phases_b.lead_shoulder_idx,
        fps=60.0,
    )
    ta = phase_key_times_sec(phases_a, 30.0)
    tb = phase_key_times_sec(phases_b, 60.0)
    deltas = phase_timing_deltas_sec(ta, tb)
    assert all(v < 1e-6 for v in deltas.values())


@needs_ffmpeg
@pytest.mark.parametrize("case", _timing_cases(), ids=lambda c: c.get("id", "case"))
def test_ac_b7_v1_v2_phase_timing_within_tolerance(case: dict) -> None:
    """AC-B7 · 真视频 V1 preprocess vs V2 preprocess 阶段时刻对齐。"""
    video = resolve_manifest_fixture_video(case, real_dir=REAL_DIR)
    if video is None:
        pytest.skip(f"缺少 fixture：{case.get('fixture_file')}")

    pack = _timing_pack()
    max_delta = float(pack.get("max_phase_delta_sec") or DEFAULT_MAX_PHASE_DELTA_SEC)

    from tests.timing_regression_helpers import compare_preprocess_v1_v2_timing

    try:
        snap_v1, snap_v2, deltas = compare_preprocess_v1_v2_timing(
            video,
            max_delta_sec=max_delta,
        )
    except Exception as exc:
        from app.errors import PoseModelError

        if isinstance(exc, PoseModelError):
            pytest.skip(f"MediaPipe 不可用：{exc}")
        raise
    assert snap_v2.fps >= snap_v1.fps, (
        f"expected v2 fps >= v1, got v2={snap_v2.fps} v1={snap_v1.fps}"
    )
    assert max(deltas.values()) <= max_delta
