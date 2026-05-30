#!/usr/bin/env python3
"""将 ``pro_clip_score_rank.py`` 的最高分候选写入 Demo Pro 镜头（替换占位 92 分）.

默认 **dry-run** 只打印将写入的字段；加 ``--apply`` 才改数据库。
视频须已在 MinIO/COS 且 ``video_url`` 域名在 ``PRO_CLIP_ALLOWED_VIDEO_DOMAINS`` 白名单内。

用法
----
    cd backend
    uv run python ../tools/scripts/apply_pro_clip_winner.py \\
        --rank-csv ../ai_engine/reports/pro_clip_rank.csv \\
        --min-score 70 \\
        --dry-run

    # 确认后写库（本地 docker compose）
    uv run python ../tools/scripts/apply_pro_clip_winner.py \\
        --rank-csv ../ai_engine/reports/pro_clip_rank.csv \\
        --min-score 70 \\
        --apply \\
        --video-url https://api.birdieai.cn/minio/xiaoniao-videos/pro-clips/winner.mp4
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if not BACKEND.is_dir():
    ROOT = Path(__file__).resolve().parents[1]
    BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def _load_top_row(path: Path, min_score: int) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if row.get("status") != "completed":
            continue
        score_raw = row.get("overall_score") or ""
        if not score_raw.strip().isdigit():
            continue
        score = int(score_raw)
        if score < min_score:
            continue
        return row
    raise SystemExit(f"[fatal] 无 completed 且 overall>={min_score} 的行: {path}")


def _phase_scores_for_snapshot(phase_json: str) -> dict:
    try:
        raw = json.loads(phase_json or "{}")
    except json.JSONDecodeError:
        return {}
    out: dict[str, int] = {}
    if not isinstance(raw, dict):
        return out
    for key, val in raw.items():
        if isinstance(val, dict) and isinstance(val.get("score"), (int, float)):
            out[key] = int(val["score"])
        elif isinstance(val, (int, float)):
            out[key] = int(val)
    return out


async def _apply(row: dict[str, str], video_url: str) -> None:
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.pro_library import ProPlayer, ProSwingClip
    from app.services import pro_library_service

    phase_snap = _phase_scores_for_snapshot(row.get("phase_scores_json") or "{}")
    overall = int(row["overall_score"])
    engine_version = row.get("engine_version") or "v2"

    async with AsyncSessionLocal() as db:
        await pro_library_service.seed_initial_pros(db)
        player_row = await db.execute(
            select(ProPlayer).where(ProPlayer.name == "Demo Pro · 内置示例")
        )
        player = player_row.scalar_one_or_none()
        if player is None:
            raise RuntimeError("Demo Pro 不存在，请先 seed_initial_pros")

        clip_row = await db.execute(
            select(ProSwingClip)
            .where(
                ProSwingClip.pro_player_id == player.id,
                ProSwingClip.is_published.is_(True),
            )
            .limit(1)
        )
        clip = clip_row.scalar_one_or_none()
        if clip is None:
            raise RuntimeError("Demo Pro 无 published clip")

        snap = dict(clip.features_snapshot or {})
        snap.update(phase_snap)

        clip.video_url = video_url
        clip.overall_score = overall
        clip.engine_version = engine_version
        clip.club_type = row.get("club_type") or clip.club_type
        clip.camera_angle = row.get("camera_angle") or clip.camera_angle
        clip.source_credit = row.get("source_credit") or clip.source_credit
        clip.source_url = row.get("source_url") or clip.source_url
        clip.license_status = row.get("license_status") or clip.license_status
        clip.description = (
            f"引擎标定高分参考 · {row.get('player_name', '')} · "
            f"overall={overall} · candidate={row.get('candidate_id', '')}"
        )
        clip.features_snapshot = snap

        player.name = row.get("player_name") or player.name
        player.short_bio = (
            f"高分参考镜头（overall {overall}）；"
            f"来源见 source_credit。非巡回赛官方代言。"
        )

        await db.commit()
        print(
            f"[ok] 已更新 clip_id={clip.id} player_id={player.id} "
            f"overall={overall} video_url={video_url}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rank-csv", required=True, help="pro_clip_score_rank 输出 CSV")
    parser.add_argument("--min-score", type=int, default=70)
    parser.add_argument(
        "--video-url",
        help="入库 video_url（须在白名单域名）；默认用 rank CSV 的 resolved_video_url",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="真正写库；缺省仅 dry-run",
    )
    args = parser.parse_args()

    row = _load_top_row(Path(args.rank_csv), args.min_score)
    video_url = args.video_url or row.get("resolved_video_url") or row.get("video_url")
    if not video_url:
        print("[fatal] 无 video_url，请 --video-url 或 manifest 提供", file=sys.stderr)
        return 2

    payload = {
        "candidate_id": row.get("candidate_id"),
        "player_name": row.get("player_name"),
        "overall_score": row.get("overall_score"),
        "engine_version": row.get("engine_version"),
        "issue_types": row.get("issue_types"),
        "video_url": video_url,
        "source_credit": row.get("source_credit"),
        "source_url": row.get("source_url"),
        "license_status": row.get("license_status"),
    }
    print("[plan] 将写入 Demo Pro 镜头：")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not args.apply:
        print("\n[dry-run] 加 --apply 才会改库。")
        print(
            "若 resolved URL 是 Wikimedia/外站，请先上传到 MinIO 再 --video-url 指向自有域名。"
        )
        return 0

    asyncio.run(_apply(row, video_url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
