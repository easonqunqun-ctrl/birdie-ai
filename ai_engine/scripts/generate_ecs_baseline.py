#!/usr/bin/env python3
"""重新生成 ECS v1 CI baseline_snapshot.json（ENG-04 维护脚本）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ecs.regression import default_ecs_v1_dir, generate_snapshot, load_manifest  # noqa: E402
from tests.ecs.pose_profiles import build_pose_profile  # noqa: E402


def main() -> int:
    ecs_dir = default_ecs_v1_dir()
    manifest = load_manifest(ecs_dir / "manifest.json")
    snap = generate_snapshot(manifest, build_pose_profile)
    snap["generated_at"] = "2026-05-22"
    snap["git_hint"] = "regenerate via scripts/generate_ecs_baseline.py"
    out = ecs_dir / "baseline_snapshot.json"
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    for cid, payload in snap["clips"].items():
        print(f"  {cid}: overall={payload['overall']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
