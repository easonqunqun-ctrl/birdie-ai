"""P2-M7-R1 · rotation/perception 回归门禁（manifest R2/R3 合成子集）。

真视频片（Rose / 室内 7 铁）待 ECS 入库后挂到 manifest；当前用合成 + Nelly 特征向量守门。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pipeline.diagnose import diagnose
from app.pipeline.feature_measurability import (
    WARN_ROTATION_SANITY,
    sanitize_features,
)
from app.pipeline.real_pipeline_v2 import diagnose_v2
from tests.test_diagnose import _fake_phases, _ideal_features
from tests.test_nelly_dtl_scoring import NELLY_LIVE, NELLY_SNAPSHOT

from app.pipeline.rotation_issue_copy import ROTATION_ISSUE_TYPES

_MANIFEST = Path(__file__).parent / "fixtures" / "rotation_regression_manifest.json"


def test_manifest_loads() -> None:
    data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert data["version"] in ("v0.1", "v0.2", "v0.3", "v0.4")
    assert "R2_dtl_broadcast" in data["packs"]
    assert "R1_face_on_repeatability" in data["packs"]
    assert "R3_preprocess_v2_timing" in data["packs"]
    assert "R3_synthetic" in data["packs"]


@pytest.mark.parametrize(
    "raw",
    [NELLY_LIVE, NELLY_SNAPSHOT],
    ids=["nelly_live", "nelly_snapshot"],
)
def test_r2_dtl_no_rotation_issues(raw: dict[str, float]) -> None:
    """R2 · DTL 转播：旋转类 issue 不得 severity≥medium（此处直接零旋转 issue）。"""
    features, _ = sanitize_features(raw, camera_angle="down_the_line")
    for fn in diagnose, diagnose_v2:
        issues = fn(features, _fake_phases(), camera_angle="down_the_line")
        hit = ROTATION_ISSUE_TYPES & {i.type for i in issues}
        assert not hit, f"{fn.__name__} rotation issues: {hit}"


def test_r2_dtl_expects_measurability_warnings() -> None:
    _, warns = sanitize_features(NELLY_LIVE, camera_angle="down_the_line")
    assert WARN_ROTATION_SANITY in warns or "angle_limited_scoring" in warns or len(warns) >= 1


def test_r3_x_factor_155_no_flat_shoulder_in_issues() -> None:
    """R3 · F-High：荒谬 x_factor 进 sanitize 后不得触发 flat_shoulder。"""
    feats = _ideal_features()
    feats.update(
        {
            "shoulder_rotation_top": 120.0,
            "hip_rotation_top": 5.0,
            "x_factor": 155.0,
        }
    )
    cleaned, warns = sanitize_features(feats, camera_angle="face_on")
    assert "x_factor" not in cleaned
    assert WARN_ROTATION_SANITY in warns
    issues = diagnose(cleaned, _fake_phases(), camera_angle="face_on")
    assert "flat_shoulder" not in {i.type for i in issues}


def test_r3_under_plus_steep_contradiction_dropped() -> None:
    """R3 · F-Contra：under_rotation + steep_shoulder 不得共存；并补 rotation warning。"""
    feats = _ideal_features()
    feats.update(
        {
            "shoulder_rotation_top": 60.0,
            "hip_rotation_top": 55.0,
            "x_factor": 5.0,
        }
    )
    for fn in diagnose, diagnose_v2:
        guard: list[str] = []
        issues = fn(
            feats,
            _fake_phases(),
            camera_angle="face_on",
            guard_warnings_out=guard,
        )
        types = {i.type for i in issues}
        assert not ("under_rotation" in types and "steep_shoulder" in types)
        assert WARN_ROTATION_SANITY in guard


def test_r3_high_wrist_low_shoulder_no_under_rotation() -> None:
    """R3 · F-Low · AC-A2：高腕 + 极低肩转不得 under_rotation。"""
    feats = _ideal_features()
    feats["shoulder_rotation_top"] = 10.0
    feats["top_wrist_position"] = 0.18
    issues = diagnose(feats, _fake_phases(), camera_angle="face_on")
    assert "under_rotation" not in {i.type for i in issues}


def test_r2_face_on_clear_turn_not_severely_under_rotated() -> None:
    """R2 · 明显转肩 face-on：sanitize 后肩转应 ≥45° 或旋转键被剔除（不得 3° 进诊断）。"""
    feats = _ideal_features()
    feats.update(
        {
            "shoulder_rotation_top": 72.0,
            "hip_rotation_top": 38.0,
            "x_factor": 34.0,
            "top_wrist_position": 0.28,
        }
    )
    cleaned, _ = sanitize_features(feats, camera_angle="face_on")
    shoulder = cleaned.get("shoulder_rotation_top")
    if shoulder is not None:
        assert shoulder >= 45.0
    issues = diagnose(cleaned, _fake_phases(), camera_angle="face_on")
    under = [i for i in issues if i.type == "under_rotation"]
    assert not under or all(i.severity != "high" for i in under)
