"""ENG-04 标定集 issue 检测 F1 评估 + 回归门禁纯逻辑单测。"""

from __future__ import annotations

import json

from app.ecs.calibration import (
    DEFAULT_MAX_F1_DROP,
    IssueDetectionStats,
    compute_detection_stats,
    evaluate_f1_regression,
    macro_f1,
    per_type_f1,
    regression_level,
)
from app.ecs.regression import default_ecs_v1_dir
from app.pipeline.diagnose import diagnose
from app.pipeline.features import extract_features
from app.pipeline.phases import segment_phases
from tests.ecs.pose_profiles import build_pose_profile


def test_perfect_detection_gives_f1_one() -> None:
    gt = {"c1": {"sway"}, "c2": {"early_extension"}}
    pred = {"c1": {"sway"}, "c2": {"early_extension"}}
    stats = compute_detection_stats(pred, gt)
    assert stats["sway"].f1 == 1.0
    assert stats["early_extension"].f1 == 1.0
    assert macro_f1(stats) == 1.0


def test_false_positive_lowers_precision() -> None:
    gt = {"c1": set(), "c2": {"sway"}}
    pred = {"c1": {"sway"}, "c2": {"sway"}}  # c1 误报 sway
    stats = compute_detection_stats(pred, gt)
    s = stats["sway"]
    assert s.tp == 1 and s.fp == 1 and s.fn == 0
    assert s.precision == 0.5
    assert s.recall == 1.0


def test_false_negative_lowers_recall() -> None:
    gt = {"c1": {"sway"}, "c2": {"sway"}}
    pred = {"c1": {"sway"}, "c2": set()}  # c2 漏检
    stats = compute_detection_stats(pred, gt)
    s = stats["sway"]
    assert s.tp == 1 and s.fp == 0 and s.fn == 1
    assert s.recall == 0.5


def test_macro_f1_ignores_unsupported_types() -> None:
    # noise 类型只在预测里出现、ground truth 从无 → support=0，不进 macro 分母
    gt = {"c1": {"sway"}}
    pred = {"c1": {"sway", "noise"}}
    stats = compute_detection_stats(pred, gt)
    assert stats["noise"].support == 0
    assert macro_f1(stats) == 1.0  # 只看 sway


def test_per_type_f1_only_supported() -> None:
    gt = {"c1": {"sway"}}
    pred = {"c1": {"sway", "noise"}}
    stats = compute_detection_stats(pred, gt)
    f1_map = per_type_f1(stats)
    assert "sway" in f1_map
    assert "noise" not in f1_map


def test_f1_regression_flags_drop_over_threshold() -> None:
    gt = {"c1": {"sway"}, "c2": {"sway"}}
    pred = {"c1": {"sway"}, "c2": set()}  # F1 = 2*1*0.5/1.5 = 0.667
    stats = compute_detection_stats(pred, gt)
    baseline = {"sway": 1.0}
    findings = evaluate_f1_regression(stats, baseline, max_f1_drop=DEFAULT_MAX_F1_DROP)
    assert regression_level(findings) == "red"
    assert findings[0].issue_type == "sway"


def test_f1_regression_passes_within_threshold() -> None:
    gt = {"c1": {"sway"}, "c2": {"sway"}}
    pred = {"c1": {"sway"}, "c2": {"sway"}}  # F1 = 1.0
    stats = compute_detection_stats(pred, gt)
    baseline = {"sway": 1.0}
    findings = evaluate_f1_regression(stats, baseline)
    assert regression_level(findings) == "pass"
    assert findings == []


def test_f1_regression_disappeared_type_is_red() -> None:
    # baseline 有该类型，当前完全检不出 → F1=0 必标红
    gt = {"c1": {"sway"}}
    pred = {"c1": set()}
    stats = compute_detection_stats(pred, gt)
    findings = evaluate_f1_regression(stats, {"sway": 0.9})
    assert regression_level(findings) == "red"
    assert findings[0].current_f1 == 0.0


def test_empty_stats_macro_zero() -> None:
    assert macro_f1({}) == 0.0


def test_issue_detection_stats_zero_division_safe() -> None:
    s = IssueDetectionStats(issue_type="x", tp=0, fp=0, fn=0)
    assert s.precision == 0.0
    assert s.recall == 0.0
    assert s.f1 == 0.0
    assert s.support == 0


# ============================================================
# 端到端 CI 回归：跑随仓库分发的 stub 标定集，门禁不得标红
# （对齐 test_ecs_regression.py：合成 Pose → diagnose → F1 对照 baseline）
# ============================================================


def _predict_from_profile(profile: str) -> set[str]:
    pose = build_pose_profile(profile)
    phases = segment_phases(pose)
    features = extract_features(pose.keypoints, phases)
    return {i.type for i in diagnose(features, phases)}


def test_shipped_calibration_stub_has_no_regression() -> None:
    ecs_dir = default_ecs_v1_dir()
    manifest = json.loads((ecs_dir / "calibration_manifest.json").read_text(encoding="utf-8"))
    baseline = json.loads((ecs_dir / "calibration_baseline.json").read_text(encoding="utf-8"))
    baseline_f1 = {str(k): float(v) for k, v in baseline["per_type_f1"].items()}

    predicted: dict[str, set[str]] = {}
    ground_truth: dict[str, set[str]] = {}
    for clip in manifest["clips"]:
        cid = str(clip["ecs_clip_id"])
        ground_truth[cid] = set(clip["expected_issues"])
        predicted[cid] = _predict_from_profile(str(clip["pose_profile"]))

    stats = compute_detection_stats(predicted, ground_truth)
    findings = evaluate_f1_regression(stats, baseline_f1)
    assert regression_level(findings) == "pass", [f.message for f in findings]
    assert macro_f1(stats) == baseline["macro_f1"]
