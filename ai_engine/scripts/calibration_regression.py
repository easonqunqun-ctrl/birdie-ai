#!/usr/bin/env python3
"""ENG-04 · 标定集 issue 检测 F1 回归门禁（CLI 封装）。

定位
----
``scripts/generate_ecs_baseline.py`` + ``app/ecs/regression.py`` 守的是 **scoring 漂移**
（overall / 阶段分）。本脚本守的是另一条线：**issue 检测**的 F1 不得相对 baseline 跌超过
门禁（默认 5%），对应 ``docs/release-notes/wait-for-triggers-checklist.md`` §2.7 ENG-04。

触发条件（外部）
----------------
争议样本累计 ≥20（来自 ENG-06 周报）→ 入 ``docs/20`` 标定集 → 改 YAML / 规则阈值前后
各跑一次本脚本，确认没有把某个 issue 类型调没了。

标定集 manifest 格式
--------------------
``{
  "version": "...",
  "description": "...",
  "clips": [
    {"ecs_clip_id": "...", "pose_profile": "sway_swing", "expected_issues": ["sway"]},
    ...
  ]
}``

- ``pose_profile``：与 ``tests/ecs/pose_profiles.py::build_pose_profile`` 对齐的合成 Pose
  名（当前标定集为合成样本；接入真实授权样本时改这里的 pose 来源即可，评估逻辑不变）。
- ``expected_issues``：**人工标注**该样本应当检出的 issue 类型集合（ground truth）。

用法
----
首次 / 调参基准——把当前输出落成 baseline::

    python scripts/calibration_regression.py \\
        --manifest tests/ecs/v1/calibration_manifest.json \\
        --out-baseline tests/ecs/v1/calibration_baseline.json

改阈值后回归门禁（任一类型 F1 跌 >5% → 退出码 1，CI 红灯）::

    python scripts/calibration_regression.py \\
        --manifest tests/ecs/v1/calibration_manifest.json \\
        --baseline tests/ecs/v1/calibration_baseline.json \\
        --report-md reports/calibration_regression.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ecs.calibration import (  # noqa: E402
    DEFAULT_MAX_F1_DROP,
    IssueDetectionStats,
    compute_detection_stats,
    evaluate_f1_regression,
    macro_f1,
    per_type_f1,
    regression_level,
)
from app.pipeline.diagnose import diagnose  # noqa: E402
from app.pipeline.features import extract_features  # noqa: E402
from app.pipeline.phases import segment_phases  # noqa: E402
from tests.ecs.pose_profiles import build_pose_profile  # noqa: E402


def _predict_issue_types(pose_profile: str, *, min_confidence: float) -> set[str]:
    """跑 phases → features → diagnose 子链路，返回检出的 issue 类型集合。"""
    pose = build_pose_profile(pose_profile)
    phases = segment_phases(pose)
    features = extract_features(pose.keypoints, phases)
    issues = diagnose(features, phases, min_confidence=min_confidence)
    return {i.type for i in issues}


def _load_manifest(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not raw.get("clips"):
        sys.stderr.write(f"[fatal] manifest 无 clips：{path}\n")
        sys.exit(2)
    return raw


def _run(
    manifest: dict, *, min_confidence: float
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    predicted: dict[str, set[str]] = {}
    ground_truth: dict[str, set[str]] = {}
    for clip in manifest["clips"]:
        cid = str(clip["ecs_clip_id"])
        profile = str(clip["pose_profile"])
        ground_truth[cid] = set(clip.get("expected_issues") or [])
        predicted[cid] = _predict_issue_types(profile, min_confidence=min_confidence)
    return predicted, ground_truth


def _write_report_md(
    stats: dict[str, IssueDetectionStats],
    macro: float,
    findings: list,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# ENG-04 标定集 issue 检测 F1 回归报告", ""]
    lines.append(f"- **macro F1（有标注类型）**：{macro:.4f}")
    lines.append(f"- 类型数：{len([s for s in stats.values() if s.support > 0])}（有标注）")
    lines.append("")
    lines.append("## 逐类型准召")
    lines.append("")
    lines.append("| issue_type | support | TP | FP | FN | precision | recall | F1 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for t in sorted(stats):
        s = stats[t]
        lines.append(
            f"| `{t}` | {s.support} | {s.tp} | {s.fp} | {s.fn} | "
            f"{s.precision:.3f} | {s.recall:.3f} | {s.f1:.3f} |"
        )
    lines.append("")
    lines.append("## 回归门禁")
    lines.append("")
    if findings:
        lines.append("**❌ 标红**（相对 baseline F1 跌幅超门禁）：")
        for f in findings:
            lines.append(f"- {f.message}")
    else:
        lines.append("✅ 无类型 F1 跌幅超门禁。")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="ENG-04 标定集 issue 检测 F1 回归门禁")
    parser.add_argument(
        "--manifest",
        default="tests/ecs/v1/calibration_manifest.json",
        help="标定集 manifest（含 expected_issues ground truth）",
    )
    parser.add_argument(
        "--baseline",
        help="baseline F1 JSON；提供则做回归门禁（任一类型跌幅超阈值 → 退出码 1）",
    )
    parser.add_argument(
        "--out-baseline",
        help="把当前 per-type F1 落成新 baseline JSON",
    )
    parser.add_argument("--report-md", help="可选 markdown 报告输出路径")
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="diagnose 展示置信度阈值（默认 0.6，对齐 MIN_DISPLAY_CONFIDENCE）",
    )
    parser.add_argument(
        "--max-f1-drop",
        type=float,
        default=DEFAULT_MAX_F1_DROP,
        help=f"F1 回归门禁跌幅（默认 {DEFAULT_MAX_F1_DROP}）",
    )
    args = parser.parse_args()

    manifest = _load_manifest(Path(args.manifest))
    predicted, ground_truth = _run(manifest, min_confidence=args.min_confidence)
    stats = compute_detection_stats(predicted, ground_truth)
    macro = macro_f1(stats)
    cur_f1 = per_type_f1(stats)

    sys.stderr.write(f"[info] manifest={manifest.get('version')} clips={len(manifest['clips'])}\n")
    sys.stderr.write(f"[info] macro F1（有标注类型）= {macro:.4f}\n")
    for t in sorted(stats):
        s = stats[t]
        sys.stderr.write(
            f"  {t}: P={s.precision:.3f} R={s.recall:.3f} F1={s.f1:.3f} "
            f"(tp={s.tp} fp={s.fp} fn={s.fn})\n"
        )

    if args.out_baseline:
        out = Path(args.out_baseline)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {"version": manifest.get("version"), "macro_f1": macro, "per_type_f1": cur_f1},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        sys.stderr.write(f"[done] baseline 写入 {out}\n")

    findings: list = []
    if args.baseline:
        base_raw = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        baseline_f1 = {str(k): float(v) for k, v in base_raw["per_type_f1"].items()}
        findings = evaluate_f1_regression(stats, baseline_f1, max_f1_drop=args.max_f1_drop)

    if args.report_md:
        _write_report_md(stats, macro, findings, Path(args.report_md))
        sys.stderr.write(f"[done] 报告写入 {args.report_md}\n")

    if args.baseline:
        level = regression_level(findings)
        if level == "red":
            sys.stderr.write("\n[FAIL] ❌ issue 检测 F1 回归门禁标红：\n")
            for f in findings:
                sys.stderr.write(f"  - {f.message}\n")
            return 1
        sys.stderr.write("\n[PASS] ✅ 无 F1 回归。\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
