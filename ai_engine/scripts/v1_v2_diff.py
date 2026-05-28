#!/usr/bin/env python3
"""W6 ENG-A3 · 离线 V1 / V2 引擎一致性对比脚本.

为什么需要这个脚本
------------------
W5 让 V2 用 YAML 重诊 issues 后，**理论上** V1/V2 输出应当高度一致：

- ``overall_score`` 完全相同（评分链路没动）
- ``issues`` 集合高度重合（同一阈值同一互斥矩阵）

但「理论」不等于「线上」——可能有阈值精度差、phase_anchor 选错、locale 占位符
没渲染等隐患。把 V2 灰度从 5% 推到 50%/100% 之前，应当有定量证据证明
V1/V2 输出差异在可接受范围。本脚本就是这个 go/no-go 凭证。

用法
----
对一组视频 URL 各调一次 ai_engine ``/analyze``（强制 v1）+ 一次（强制 v2），
diff 结果并输出 CSV + 汇总 markdown。

    # 从 CSV（列: analysis_id,video_url）
    python v1_v2_diff.py \\
        --engine-url http://localhost:9100 \\
        --input-csv samples.csv \\
        --out-csv reports/v1_v2_diff.csv \\
        --report-md reports/v1_v2_diff.md

    # 或直接给 URL 列表
    python v1_v2_diff.py --engine-url http://ai_engine:9000 \\
        --input-urls "https://.../a.mp4,https://.../b.mp4" \\
        --out-csv /tmp/diff.csv --report-md /tmp/diff.md

线上验证流程建议
----------------
1. CVM ssh 进 backend 容器拉最近 20 个 success 的 swing_analysis：
   ``SELECT id, video_url FROM swing_analyses WHERE status='COMPLETED'
   ORDER BY created_at DESC LIMIT 20;``
2. 导出 CSV 放到 ai_engine 容器
3. 容器内跑 ``python /app/scripts/v1_v2_diff.py --engine-url http://localhost:9000 ...``
4. 看 ``score_exact_match_rate`` 应 100%（评分链路没动）
   ``issue_types_jaccard_p50`` 期望 ≥0.9（W5 V1 全集已迁，只差互斥/精度噪声）
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.stderr.write("[fatal] 请先 pip install httpx\n")
    raise


@dataclass(frozen=True)
class Sample:
    analysis_id: str
    video_url: str


@dataclass
class DiffRow:
    analysis_id: str
    video_url: str
    v1_status: str
    v2_status: str
    v1_overall_score: float | None
    v2_overall_score: float | None
    score_exact_match: bool
    v1_issue_types: list[str]
    v2_issue_types: list[str]
    common_types: list[str]
    v1_only_types: list[str]
    v2_only_types: list[str]
    issue_types_jaccard: float

    @property
    def issue_types_exact_match(self) -> bool:
        return set(self.v1_issue_types) == set(self.v2_issue_types)


def _read_samples(args: argparse.Namespace) -> list[Sample]:
    samples: list[Sample] = []
    if args.input_csv:
        with open(args.input_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=1):
                aid = row.get("analysis_id") or f"sample_{i}"
                url = row.get("video_url")
                if not url:
                    sys.stderr.write(
                        f"[warn] row {i} 缺 video_url, 跳过\n"
                    )
                    continue
                samples.append(Sample(analysis_id=aid, video_url=url))
    if args.input_urls:
        for i, url in enumerate(
            [u.strip() for u in args.input_urls.split(",") if u.strip()], start=1
        ):
            samples.append(
                Sample(analysis_id=f"url_{i}_{uuid.uuid4().hex[:6]}", video_url=url)
            )
    if not samples:
        sys.stderr.write("[fatal] 未提供任何样本（--input-csv / --input-urls）\n")
        sys.exit(2)
    return samples


def _analyze_once(
    client: httpx.Client,
    engine_url: str,
    sample: Sample,
    force: str,
    timeout: float,
) -> dict:
    """调一次 /analyze，失败时返回 {"status":"client_error","error_message": str(e)}."""
    payload = {
        "analysis_id": f"{sample.analysis_id}__{force}",
        "video_url": sample.video_url,
        "force_engine_version": force,
    }
    try:
        resp = client.post(f"{engine_url}/analyze", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "client_error",
            "error_message": repr(exc),
            "overall_score": None,
            "issues": [],
        }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return round(len(a & b) / len(a | b), 4)


def _diff_one(sample: Sample, v1: dict, v2: dict) -> DiffRow:
    v1_types = sorted({i.get("type") for i in v1.get("issues") or [] if i.get("type")})
    v2_types = sorted({i.get("type") for i in v2.get("issues") or [] if i.get("type")})
    return DiffRow(
        analysis_id=sample.analysis_id,
        video_url=sample.video_url,
        v1_status=v1.get("status", "?"),
        v2_status=v2.get("status", "?"),
        v1_overall_score=v1.get("overall_score"),
        v2_overall_score=v2.get("overall_score"),
        score_exact_match=v1.get("overall_score") == v2.get("overall_score"),
        v1_issue_types=v1_types,
        v2_issue_types=v2_types,
        common_types=sorted(set(v1_types) & set(v2_types)),
        v1_only_types=sorted(set(v1_types) - set(v2_types)),
        v2_only_types=sorted(set(v2_types) - set(v1_types)),
        issue_types_jaccard=_jaccard(set(v1_types), set(v2_types)),
    )


def _write_csv(rows: list[DiffRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "analysis_id",
                "video_url",
                "v1_status",
                "v2_status",
                "v1_overall_score",
                "v2_overall_score",
                "score_exact_match",
                "issue_types_jaccard",
                "issue_types_exact_match",
                "v1_issue_types",
                "v2_issue_types",
                "common_types",
                "v1_only_types",
                "v2_only_types",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r.analysis_id,
                    r.video_url,
                    r.v1_status,
                    r.v2_status,
                    r.v1_overall_score,
                    r.v2_overall_score,
                    r.score_exact_match,
                    r.issue_types_jaccard,
                    r.issue_types_exact_match,
                    "|".join(r.v1_issue_types),
                    "|".join(r.v2_issue_types),
                    "|".join(r.common_types),
                    "|".join(r.v1_only_types),
                    "|".join(r.v2_only_types),
                ]
            )


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    vs = sorted(values)
    idx = int(p / 100 * (len(vs) - 1))
    return vs[idx]


def _summarize(rows: list[DiffRow]) -> dict:
    success = [r for r in rows if r.v1_status != "client_error" and r.v2_status != "client_error"]
    score_matches = [r for r in success if r.score_exact_match]
    type_matches = [r for r in success if r.issue_types_exact_match]
    jaccards = [r.issue_types_jaccard for r in success]
    v1_only_counter: Counter[str] = Counter()
    v2_only_counter: Counter[str] = Counter()
    for r in success:
        v1_only_counter.update(r.v1_only_types)
        v2_only_counter.update(r.v2_only_types)
    return {
        "total_samples": len(rows),
        "success_pairs": len(success),
        "client_errors": len(rows) - len(success),
        "score_exact_match_rate": round(len(score_matches) / len(success), 4) if success else 0.0,
        "issue_types_exact_match_rate": round(len(type_matches) / len(success), 4) if success else 0.0,
        "issue_types_jaccard_p50": _percentile(jaccards, 50),
        "issue_types_jaccard_p10": _percentile(jaccards, 10),
        "v1_only_top": v1_only_counter.most_common(10),
        "v2_only_top": v2_only_counter.most_common(10),
    }


def _write_md(rows: list[DiffRow], summary: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# V1 / V2 引擎一致性 diff 报告")
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    lines.append(f"- 样本总数：**{summary['total_samples']}**")
    lines.append(f"- 成功配对：{summary['success_pairs']}（client_error：{summary['client_errors']}）")
    lines.append(f"- **overall_score 完全一致率**：{summary['score_exact_match_rate'] * 100:.2f}%")
    lines.append(
        f"- **issue 类型集合完全一致率**：{summary['issue_types_exact_match_rate'] * 100:.2f}%"
    )
    lines.append(f"- issue 类型 Jaccard P50：{summary['issue_types_jaccard_p50']:.3f}")
    lines.append(f"- issue 类型 Jaccard P10：{summary['issue_types_jaccard_p10']:.3f}（最差 10% 样本）")
    lines.append("")
    lines.append("## 仅 V1 触发的 issue type（Top 10）")
    lines.append("")
    if summary["v1_only_top"]:
        for t, n in summary["v1_only_top"]:
            lines.append(f"- `{t}`: {n}")
    else:
        lines.append("- _无_")
    lines.append("")
    lines.append("## 仅 V2 触发的 issue type（Top 10）")
    lines.append("")
    if summary["v2_only_top"]:
        for t, n in summary["v2_only_top"]:
            lines.append(f"- `{t}`: {n}")
    else:
        lines.append("- _无_")
    lines.append("")
    lines.append("## go / no-go 建议")
    lines.append("")
    rate = summary["issue_types_exact_match_rate"]
    if rate >= 0.9:
        lines.append("- ✅ issue 类型一致率 ≥90%，**可推进灰度到下一档**（例如 5→25→50）")
    elif rate >= 0.7:
        lines.append(
            "- ⚠️ issue 类型一致率 70~90%，**建议先看 v1_only / v2_only top 是哪几条**，"
            "确认是规则阈值还是互斥差异，修了再推进"
        )
    else:
        lines.append(
            "- ❌ issue 类型一致率 <70%，**先别推进**，V1/V2 输出差异过大；"
            "回查 v2_starter.yaml 阈值 / mutually_exclusive_with 是否漏配"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="V1/V2 ai_engine 一致性 diff")
    parser.add_argument(
        "--engine-url",
        default="http://localhost:9100",
        help="ai_engine 端点；容器内常为 http://localhost:9000，宿主机为 http://localhost:9100",
    )
    parser.add_argument("--input-csv", help="CSV 路径；列：analysis_id,video_url")
    parser.add_argument("--input-urls", help="逗号分隔的 video URL 列表")
    parser.add_argument(
        "--out-csv",
        default="reports/v1_v2_diff.csv",
        help="逐样本 diff CSV 输出路径",
    )
    parser.add_argument(
        "--report-md",
        default="reports/v1_v2_diff.md",
        help="汇总 markdown 报告输出路径",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="单次 /analyze 超时秒数（单视频 MediaPipe ~30~60s）",
    )
    args = parser.parse_args()

    samples = _read_samples(args)
    sys.stderr.write(f"[info] 准备跑 {len(samples)} 个样本 × 2 (v1+v2)\n")

    rows: list[DiffRow] = []
    with httpx.Client() as client:
        for i, sample in enumerate(samples, start=1):
            sys.stderr.write(f"  [{i}/{len(samples)}] {sample.analysis_id} → v1 ...\n")
            v1 = _analyze_once(client, args.engine_url, sample, "v1", args.timeout)
            sys.stderr.write(f"  [{i}/{len(samples)}] {sample.analysis_id} → v2 ...\n")
            v2 = _analyze_once(client, args.engine_url, sample, "v2", args.timeout)
            rows.append(_diff_one(sample, v1, v2))

    out_csv = Path(args.out_csv)
    report_md = Path(args.report_md)
    _write_csv(rows, out_csv)
    summary = _summarize(rows)
    _write_md(rows, summary, report_md)

    sys.stderr.write("\n[done]\n")
    sys.stderr.write(f"  CSV  → {out_csv}\n")
    sys.stderr.write(f"  REPT → {report_md}\n")
    sys.stderr.write("\n汇总（也写进 markdown）:\n")
    sys.stderr.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
