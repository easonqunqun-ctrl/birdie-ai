#!/usr/bin/env python3
"""P-02 · precheck 阈值离线评估（CLI 封装）。

定位
----
对一批**人工标注过该不该拦**的真实视频，跑 ``run_precheck`` 拿 AI 判定，算混淆矩阵，
看 **误杀**（拦了正常视频）与 **漏拦**（放过了该拦的）各多少，定位调哪个硬门槛阈值。
对应 ``docs/release-notes/wait-for-triggers-checklist.md`` §2.3 P-02。

触发条件（外部）
----------------
真实用户上传非高尔夫 / 低质视频累计 ≥5 例后，把这些样本（连同人工 pass/block 标签）
喂给本脚本。评估纯逻辑见 ``app/pipeline/precheck_eval.py``（可单测）；本脚本负责
**下载 + ffprobe + 扫描**的 I/O。

输入 CSV 格式
-------------
列（表头必须有 ``video_url`` 与 ``label``）：

    video_url,label,note
    https://.../a.mp4,block,镜头太暗的非高尔夫
    https://.../b.mp4,pass,正常侧拍 7 号铁

- ``label``：``block``（人工判该拦）/ ``pass``（人工判该放行）。

用法
----
    python scripts/precheck_threshold_eval.py \\
        --input-csv samples_labeled.csv \\
        --out-csv reports/precheck_eval.csv \\
        --report-md reports/precheck_eval.md

线上取样建议：CVM 上从 ``swing_analyses`` 拉近期被引擎拦截 / 用户投诉的样本 video_url，
人工补 label 列，放进 ai_engine 容器跑。
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline.precheck import run_precheck  # noqa: E402
from app.pipeline.precheck_eval import (  # noqa: E402
    PrecheckEvalReport,
    PrecheckEvalSample,
    evaluate,
    tuning_hint,
)


def _read_labeled(path: Path) -> list[tuple[str, str, str]]:
    """读 CSV → [(video_url, label, note)]。"""
    rows: list[tuple[str, str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            url = (row.get("video_url") or "").strip()
            label = (row.get("label") or "").strip().lower()
            note = (row.get("note") or "").strip()
            if not url:
                sys.stderr.write(f"[warn] row {i} 缺 video_url，跳过\n")
                continue
            if label not in ("block", "pass"):
                sys.stderr.write(
                    f"[warn] row {i} label='{label}' 非法（须 block/pass），跳过\n"
                )
                continue
            rows.append((url, label, note))
    if not rows:
        sys.stderr.write("[fatal] 无有效样本\n")
        sys.exit(2)
    return rows


def _run_samples(
    labeled: list[tuple[str, str, str]], *, max_scan_sec: float
) -> list[PrecheckEvalSample]:
    samples: list[PrecheckEvalSample] = []
    for i, (url, label, note) in enumerate(labeled, start=1):
        sys.stderr.write(f"  [{i}/{len(labeled)}] precheck {url} ...\n")
        result = run_precheck(
            analysis_id=f"eval_{i}", video_url=url, max_scan_sec=max_scan_sec
        )
        samples.append(
            PrecheckEvalSample(
                video_url=url,
                label=label,  # type: ignore[arg-type]
                decision=result.status,
                error_code=result.error_code,
                note=note,
            )
        )
    return samples


def _write_csv(samples: list[PrecheckEvalSample], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["video_url", "label", "decision", "outcome", "error_code", "note"]
        )
        for s in samples:
            if s.is_true_positive:
                outcome = "TP"
            elif s.is_false_positive:
                outcome = "FP_误杀"
            elif s.is_false_negative:
                outcome = "FN_漏拦"
            else:
                outcome = "TN"
            w.writerow(
                [s.video_url, s.label, s.decision, outcome, s.error_code, s.note]
            )


def _write_md(report: PrecheckEvalReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# P-02 precheck 阈值评估报告", ""]
    lines.append("## 混淆矩阵")
    lines.append("")
    lines.append("| | AI 拦截 | AI 放行 |")
    lines.append("|---|---|---|")
    lines.append(f"| **人工该拦** | TP {report.tp} | FN 漏拦 {report.fn} |")
    lines.append(f"| **人工该放** | FP 误杀 {report.fp} | TN {report.tn} |")
    lines.append("")
    lines.append(f"- 样本总数：**{report.total}**")
    lines.append(f"- 拦截精确率 precision：{report.precision:.3f}（越低误杀越多）")
    lines.append(f"- 拦截召回率 recall：{report.recall:.3f}（越低漏拦越多）")
    lines.append(f"- F1：{report.f1:.3f}")
    lines.append(f"- 误杀率：{report.false_positive_rate:.3f}")
    lines.append("")
    lines.append("## 调参方向")
    lines.append("")
    lines.append(f"- {tuning_hint(report)}")
    lines.append("")
    if report.false_positives:
        lines.append("## 误杀样本（FP，调参首要压低）")
        lines.append("")
        for s in report.false_positives:
            lines.append(f"- `{s.video_url}`（code={s.error_code}）{s.note}")
        lines.append("")
    if report.false_negatives:
        lines.append("## 漏拦样本（FN）")
        lines.append("")
        for s in report.false_negatives:
            lines.append(f"- `{s.video_url}` {s.note}")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="P-02 precheck 阈值离线评估")
    parser.add_argument(
        "--input-csv", required=True, help="标注 CSV；列：video_url,label[,note]"
    )
    parser.add_argument(
        "--out-csv",
        default="reports/precheck_eval.csv",
        help="逐样本判定 CSV 输出路径",
    )
    parser.add_argument(
        "--report-md",
        default="reports/precheck_eval.md",
        help="混淆矩阵 markdown 报告输出路径",
    )
    parser.add_argument(
        "--max-scan-sec",
        type=float,
        default=5.0,
        help="单条扫描预算秒数（对齐 O-08 的 5s 硬预检）",
    )
    args = parser.parse_args()

    labeled = _read_labeled(Path(args.input_csv))
    sys.stderr.write(f"[info] 准备评估 {len(labeled)} 条标注样本\n")
    samples = _run_samples(labeled, max_scan_sec=args.max_scan_sec)
    report = evaluate(samples)

    _write_csv(samples, Path(args.out_csv))
    _write_md(report, Path(args.report_md))

    sys.stderr.write("\n[done]\n")
    sys.stderr.write(f"  CSV  → {args.out_csv}\n")
    sys.stderr.write(f"  REPT → {args.report_md}\n")
    sys.stderr.write(
        f"  TP={report.tp} FP_误杀={report.fp} FN_漏拦={report.fn} TN={report.tn}\n"
    )
    sys.stderr.write(f"  {tuning_hint(report)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
