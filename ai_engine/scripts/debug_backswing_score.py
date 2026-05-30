#!/usr/bin/env python3
"""One-off debug: backswing phase score breakdown for a video URL."""

from __future__ import annotations

import json
import sys

from app.pipeline import preprocess
from app.pipeline.club_profiles import to_club_category
from app.pipeline.constants import FEATURES_BY_PHASE
from app.pipeline.features import extract_features
from app.pipeline.multi_swing import segment_phases_with_multi_swing
from app.pipeline.pose import estimate_poses
from app.pipeline.score_profiles import resolve_ideal
from app.pipeline.scoring import score_all_phases, score_feature


def main() -> None:
    video = sys.argv[1] if len(sys.argv) > 1 else (
        "https://api.birdieai.cn/v1/assets/video/uploads/2026/05/30/"
        "usr_shgt0rf9q0flar5d/upl_bco8wj4invt67d3f.mp4"
    )
    angle = sys.argv[2] if len(sys.argv) > 2 else "down_the_line"
    club = sys.argv[3] if len(sys.argv) > 3 else "iron_7"
    cat = to_club_category(club)

    pre = preprocess.preprocess_video(video)
    pose_result = estimate_poses(pre.normalized_video_path)
    phases, _, _ = segment_phases_with_multi_swing(pose_result, selected_swing_index=None)
    feats = extract_features(pose_result.keypoints, phases)
    ps = score_all_phases(feats, club_category=cat, camera_angle=angle)

    print("=== phase scores ===")
    print(json.dumps(ps, indent=2))

    print("\n=== backswing feature breakdown ===")
    bs_total = 0.0
    for meta in FEATURES_BY_PHASE["backswing"]:
        name = meta["name"]
        val = feats[name]
        imin, imax = resolve_ideal(name, angle, cat)
        tol = meta["tolerance"]
        s = score_feature(val, imin, imax, tol)
        width = imax - imin
        if val < imin:
            dev = (imin - val) / width
        elif val > imax:
            dev = (val - imax) / width
        else:
            dev = 0.0
        contrib = s * meta["weight"]
        bs_total += contrib
        print(
            f"{name}: value={val:.4f} ideal=[{imin},{imax}] "
            f"tol={tol} dev_ratio={dev:.3f} score={s} "
            f"weight={meta['weight']} contrib={contrib:.2f} "
            f"hard_zero={dev > tol}"
        )

    print(f"\nbackswing weighted sum = {int(round(bs_total))}")
    print("\n=== all features ===")
    print(json.dumps({k: round(v, 3) for k, v in sorted(feats.items())}, indent=2))
    print(
        f"\ntop_frame={phases.top_frame} impact={phases.impact_frame} "
        f"fps={pose_result.fps} valid_ratio={pose_result.valid_frame_ratio:.3f}"
    )


if __name__ == "__main__":
    main()
