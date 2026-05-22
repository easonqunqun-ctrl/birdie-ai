#!/usr/bin/env python3
"""临时脚本：打印 ECS 合成姿态评分，供 pose_profiles 标定。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline.features import extract_features  # noqa: E402
from app.pipeline.phases import segment_phases  # noqa: E402
from app.pipeline.scoring import score_all_phases, score_overall  # noqa: E402
from tests.ecs.pose_profiles import build_pose_profile  # noqa: E402


def main() -> int:
    for name in ("ideal_swing", "amateur_solid", "early_extension_swing", "sway_swing"):
        pose = build_pose_profile(name)
        phases = segment_phases(pose)
        feats = extract_features(pose.keypoints, phases)
        phases_scores = score_all_phases(feats)
        overall = score_overall(phases_scores)
        print(name, "overall=", overall, "phases=", phases_scores)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
