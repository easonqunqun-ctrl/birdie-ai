#!/usr/bin/env python3
"""P2-M12 · 职业镜头候选批量跑分排序（ECS / pro_library 标定用）.

对 manifest CSV 中每条视频调用 ai_engine ``POST /analyze``，按 ``overall_score`` 降序
输出 CSV + Markdown，供运营挑选「在我们规则下真正高分」的参考镜头。

**合规提醒**
------------
- **大师赛 / PGA Tour / Augusta 转播画面** 有商业版权，**不能**直接抓进产品库。
  本脚本只处理 manifest 里你已确认授权/CC 的条目。
- 入库前仍须产品+法务确认 ``license_status`` 与 ``source_credit``。

用法
----
    cd ai_engine
    uv run python scripts/pro_clip_score_rank.py \\
        --engine-url http://localhost:9100 \\
        --input-csv scripts/data/pro_clip_candidates.csv \\
        --out-csv reports/pro_clip_rank.csv \\
        --report-md reports/pro_clip_rank.md

本地 mp4（ai_engine 容器需能访问 URL）::

    uv run python scripts/pro_clip_score_rank.py \\
        --engine-url http://localhost:9100 \\
        --input-csv my_candidates.csv \\
        --serve-local ./downloads \\
        --serve-port 8765

``video_path`` 列填相对 ``--serve-local`` 的路径；脚本会转成
``http://127.0.0.1:8765/...`` 再调引擎（Docker 内引擎请改 ``--serve-host host.docker.internal``）。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import threading
import uuid
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    sys.stderr.write("[fatal] 请先 pip install httpx\n")
    raise


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    player_name: str
    video_url: str
    video_path: str
    club_type: str
    camera_angle: str
    source_credit: str
    source_url: str
    license_status: str
    notes: str


@dataclass
class RankRow:
    candidate: Candidate
    resolved_video_url: str
    status: str
    engine_version: str | None
    overall_score: int | None
    phase_scores: dict[str, Any]
    issue_types: list[str]
    issue_count: int
    quality_warnings: list[str]
    error_code: str | None
    error_message: str | None


def _read_candidates(path: Path) -> list[Candidate]:
    rows: list[Candidate] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            cid = (row.get("candidate_id") or f"row_{i}").strip()
            url = (row.get("video_url") or "").strip()
            vpath = (row.get("video_path") or "").strip()
            if not url and not vpath:
                sys.stderr.write(f"[warn] {cid}: 缺 video_url / video_path，跳过\n")
                continue
            rows.append(
                Candidate(
                    candidate_id=cid,
                    player_name=(row.get("player_name") or cid).strip(),
                    video_url=url,
                    video_path=vpath,
                    club_type=(row.get("club_type") or "iron_7").strip(),
                    camera_angle=(row.get("camera_angle") or "face_on").strip(),
                    source_credit=(row.get("source_credit") or "").strip(),
                    source_url=(row.get("source_url") or "").strip(),
                    license_status=(row.get("license_status") or "public_clip").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    if not rows:
        sys.stderr.write("[fatal] manifest 无有效行\n")
        sys.exit(2)
    return rows


def _resolve_video_url(
    cand: Candidate,
    *,
    serve_root: Path | None,
    serve_host: str,
    serve_port: int,
) -> str:
    if cand.video_url:
        return cand.video_url
    if not serve_root or not cand.video_path:
        raise ValueError(f"{cand.candidate_id}: 无 video_url 且未启用 --serve-local")
    rel = Path(cand.video_path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"{cand.candidate_id}: video_path 须为相对路径且无 ..")
    local = (serve_root / rel).resolve()
    if not local.is_file():
        raise FileNotFoundError(f"{cand.candidate_id}: 本地文件不存在 {local}")
    return f"http://{serve_host}:{serve_port}/{rel.as_posix()}"


def _start_local_server(root: Path, host: str, port: int) -> ThreadingHTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(root.resolve()))
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    sys.stderr.write(f"[info] 本地文件服务 http://{host}:{port}/ → {root.resolve()}\n")
    return server


def _analyze_once(
    client: httpx.Client,
    engine_url: str,
    cand: Candidate,
    resolved_url: str,
    *,
    force_engine: str,
    timeout: float,
) -> dict[str, Any]:
    payload = {
        "analysis_id": f"pro_rank_{cand.candidate_id}_{uuid.uuid4().hex[:8]}",
        "video_url": resolved_url,
        "club_type": cand.club_type,
        "camera_angle": cand.camera_angle,
        "mode": "full_swing",
        "force_engine_version": force_engine,
    }
    try:
        resp = client.post(f"{engine_url.rstrip('/')}/analyze", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "client_error",
            "error_message": repr(exc),
            "overall_score": None,
            "issues": [],
            "phase_scores": {},
            "quality_warnings": [],
        }


def _row_from_result(cand: Candidate, resolved_url: str, body: dict[str, Any]) -> RankRow:
    issues = body.get("issues") or []
    issue_types = sorted(
        {str(i.get("type")) for i in issues if isinstance(i, dict) and i.get("type")}
    )
    phase_scores = body.get("phase_scores") or {}
    if not isinstance(phase_scores, dict):
        phase_scores = {}
    qw = body.get("quality_warnings") or []
    if not isinstance(qw, list):
        qw = []
    overall = body.get("overall_score")
    return RankRow(
        candidate=cand,
        resolved_video_url=resolved_url,
        status=str(body.get("status") or "?"),
        engine_version=body.get("engine_version"),
        overall_score=int(overall) if isinstance(overall, (int, float)) else None,
        phase_scores=phase_scores,
        issue_types=issue_types,
        issue_count=len(issue_types),
        quality_warnings=[str(x) for x in qw],
        error_code=body.get("error_code"),
        error_message=body.get("error_message"),
    )


def _write_csv(rows: list[RankRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "rank",
                "candidate_id",
                "player_name",
                "overall_score",
                "status",
                "engine_version",
                "issue_count",
                "issue_types",
                "quality_warnings",
                "club_type",
                "camera_angle",
                "video_url",
                "resolved_video_url",
                "source_credit",
                "source_url",
                "license_status",
                "phase_scores_json",
                "notes",
                "error_code",
                "error_message",
            ]
        )
        for rank, r in enumerate(rows, start=1):
            w.writerow(
                [
                    rank,
                    r.candidate.candidate_id,
                    r.candidate.player_name,
                    r.overall_score if r.overall_score is not None else "",
                    r.status,
                    r.engine_version or "",
                    r.issue_count,
                    "|".join(r.issue_types),
                    "|".join(r.quality_warnings),
                    r.candidate.club_type,
                    r.candidate.camera_angle,
                    r.candidate.video_url,
                    r.resolved_video_url,
                    r.candidate.source_credit,
                    r.candidate.source_url,
                    r.candidate.license_status,
                    json.dumps(r.phase_scores, ensure_ascii=False),
                    r.candidate.notes,
                    r.error_code or "",
                    r.error_message or "",
                ]
            )


def _write_md(rows: list[RankRow], path: Path, *, min_score: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    completed = [r for r in rows if r.status == "completed" and r.overall_score is not None]
    high = [r for r in completed if r.overall_score >= min_score]
    lines = [
        "# 职业镜头候选 · 引擎跑分排序",
        "",
        f"- 样本数：{len(rows)}",
        f"- 成功：{len(completed)}",
        f"- overall ≥ {min_score}：{len(high)}",
        "",
        "## Top 10（completed）",
        "",
        "| rank | candidate | score | issues | warnings |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for i, r in enumerate(completed[:10], start=1):
        lines.append(
            f"| {i} | {r.candidate.player_name} (`{r.candidate.candidate_id}`) | "
            f"{r.overall_score} | {r.issue_count} | "
            f"{', '.join(r.quality_warnings[:3]) or '—'} |"
        )
    lines.extend(
        [
            "",
            "## 合规",
            "",
            "- 大师赛 / PGA 转播 **未** 列入默认 manifest；须商业授权方可入库。",
            "- 入库前确认 `source_credit` / `license_status` 与 docs/20 §5 ECS 合规一致。",
            "",
            "## 下一步",
            "",
            "```bash",
            "cd backend && uv run python ../tools/scripts/apply_pro_clip_winner.py \\",
            "  --rank-csv reports/pro_clip_rank.csv --min-score 75 --dry-run",
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="职业镜头候选批量跑分排序")
    parser.add_argument(
        "--engine-url",
        default="http://localhost:9100",
        help="ai_engine 根 URL",
    )
    parser.add_argument(
        "--input-csv",
        default="scripts/data/pro_clip_candidates.csv",
        help="manifest CSV 路径",
    )
    parser.add_argument(
        "--out-csv",
        default="reports/pro_clip_rank.csv",
        help="排序结果 CSV",
    )
    parser.add_argument(
        "--report-md",
        default="reports/pro_clip_rank.md",
        help="Markdown 摘要",
    )
    parser.add_argument(
        "--force-engine",
        choices=("v1", "v2"),
        default="v2",
        help="强制引擎版本（默认 v2 与线上一致）",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="单次 /analyze 超时秒数",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=75,
        help="Markdown 报告中「高分」阈值",
    )
    parser.add_argument(
        "--serve-local",
        type=Path,
        default=None,
        help="本地目录：为 video_path 列提供 HTTP 访问",
    )
    parser.add_argument(
        "--serve-host",
        default="127.0.0.1",
        help="本地文件服务 bind 地址",
    )
    parser.add_argument(
        "--serve-port",
        type=int,
        default=8765,
        help="本地文件服务端口",
    )
    args = parser.parse_args()

    manifest = Path(args.input_csv)
    if not manifest.is_file():
        sys.stderr.write(f"[fatal] 找不到 manifest: {manifest}\n")
        return 2

    candidates = _read_candidates(manifest)
    server: ThreadingHTTPServer | None = None
    if args.serve_local:
        server = _start_local_server(args.serve_local, args.serve_host, args.serve_port)

    rank_rows: list[RankRow] = []
    with httpx.Client(follow_redirects=True) as client:
        for i, cand in enumerate(candidates, start=1):
            try:
                resolved = _resolve_video_url(
                    cand,
                    serve_root=args.serve_local,
                    serve_host=args.serve_host,
                    serve_port=args.serve_port,
                )
            except (ValueError, FileNotFoundError) as exc:
                sys.stderr.write(f"[warn] {cand.candidate_id}: {exc}\n")
                rank_rows.append(
                    RankRow(
                        candidate=cand,
                        resolved_video_url="",
                        status="skipped",
                        engine_version=None,
                        overall_score=None,
                        phase_scores={},
                        issue_types=[],
                        issue_count=0,
                        quality_warnings=[],
                        error_code=None,
                        error_message=str(exc),
                    )
                )
                continue

            sys.stderr.write(
                f"[{i}/{len(candidates)}] {cand.candidate_id} → analyze ...\n"
            )
            body = _analyze_once(
                client,
                args.engine_url,
                cand,
                resolved,
                force_engine=args.force_engine,
                timeout=args.timeout,
            )
            row = _row_from_result(cand, resolved, body)
            rank_rows.append(row)
            sys.stderr.write(
                f"    status={row.status} overall={row.overall_score} "
                f"issues={row.issue_count}\n"
            )

    if server is not None:
        server.shutdown()

    rank_rows.sort(
        key=lambda r: (
            r.status != "completed",
            -(r.overall_score or -1),
            r.issue_count,
        )
    )

    out_csv = Path(args.out_csv)
    report_md = Path(args.report_md)
    _write_csv(rank_rows, out_csv)
    _write_md(rank_rows, report_md, min_score=args.min_score)

    sys.stderr.write(f"\n[done] CSV → {out_csv}\n")
    sys.stderr.write(f"[done] MD  → {report_md}\n")
    top = next((r for r in rank_rows if r.status == "completed"), None)
    if top:
        sys.stderr.write(
            f"[top] {top.candidate.player_name} score={top.overall_score} "
            f"id={top.candidate.candidate_id}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
