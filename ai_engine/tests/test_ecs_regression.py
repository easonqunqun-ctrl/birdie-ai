"""ECS v1 CI 回归：manifest + baseline 快照 + 漂移门禁。"""

from __future__ import annotations

from app.ecs.gates import EcsDriftGateConfig, evaluate_bulk_drift, evaluate_clip_drift
from app.ecs.regression import (
    assert_regression_pass,
    default_ecs_v1_dir,
    load_baseline_snapshot,
    load_manifest,
    run_regression,
)
from tests.ecs.pose_profiles import build_pose_profile

CI_STUB_GATE_CONFIG = EcsDriftGateConfig(teaching_overall_floor=0.0)


def test_evaluate_clip_drift_yellow_on_large_delta() -> None:
    findings = evaluate_clip_drift(
        clip_id="x",
        clip_class="top_amateur",
        baseline_overall=80,
        current_overall=86,
        baseline_phases={"setup": 80},
        current_phases={"setup": 80},
    )
    assert any(f.level == "yellow" and f.field == "overall" for f in findings)


def test_evaluate_clip_drift_red_teaching_floor() -> None:
    findings = evaluate_clip_drift(
        clip_id="t",
        clip_class="teaching",
        baseline_overall=85,
        current_overall=75,
        baseline_phases={"setup": 85},
        current_phases={"setup": 75},
    )
    assert any(f.level == "red" for f in findings)


def test_evaluate_bulk_drift_red() -> None:
    bulk = evaluate_bulk_drift(
        clip_ids=["a", "b", "c", "d"],
        overall_deltas={"a": 4, "b": 5, "c": 6, "d": 1},
    )
    assert bulk is not None
    assert bulk.level == "red"


def test_ecs_v1_ci_regression_matches_baseline() -> None:
    root = default_ecs_v1_dir()
    manifest = load_manifest(root / "manifest.json")
    baseline = load_baseline_snapshot(root / "baseline_snapshot.json")
    report = run_regression(
        manifest=manifest,
        baseline=baseline,
        build_pose=build_pose_profile,
        config=CI_STUB_GATE_CONFIG,
    )
    assert report.level in {"pass", "yellow"}
    assert_regression_pass(report)
