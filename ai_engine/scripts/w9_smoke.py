"""W9 smoke：构造不同 landmark visibility 验证 _enrich_v2 区分度.

local run on CVM:
    docker cp ai_engine/scripts/w9_smoke.py xiaoniao-ai-engine:/tmp/
    docker exec xiaoniao-ai-engine sh -c 'cd /app && uv run python /tmp/w9_smoke.py'
"""

from __future__ import annotations

import numpy as np

from app.pipeline.phases import PhaseInfo, PhaseSegmentResult
from app.pipeline.pose import (
    LANDMARK_LEFT_ANKLE,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_RIGHT_ANKLE,
    PoseResult,
)
from app.pipeline.real_pipeline import PipelineCtx
from app.pipeline.real_pipeline_v2 import _enrich_v2
from app.schemas import AnalyzeResult, IssueItem


def main() -> None:
    vis = np.full((60, 33), 0.30, dtype=np.float32)
    vis[:, LANDMARK_LEFT_ANKLE] = 0.95
    vis[:, LANDMARK_RIGHT_ANKLE] = 0.95
    vis[:, LANDMARK_LEFT_WRIST] = 0.85

    pose = PoseResult(
        keypoints=np.zeros((60, 33, 3), dtype=np.float32),
        visibility=vis,
        valid_mask=np.ones(60, dtype=bool),
        num_frames=60,
        fps=30.0,
    )
    phases = PhaseSegmentResult(
        phases={
            "setup": PhaseInfo(0, 4, 2),
            "backswing": PhaseInfo(5, 24, 15),
            "top": PhaseInfo(25, 25, 25),
            "downswing": PhaseInfo(26, 34, 30),
            "impact": PhaseInfo(35, 35, 35),
            "follow_through": PhaseInfo(36, 59, 45),
        },
        top_frame=25,
        impact_frame=35,
        swing_start=5,
        swing_end=55,
        handedness="right",
        lead_wrist_idx=LANDMARK_LEFT_WRIST,
        lead_shoulder_idx=LANDMARK_LEFT_SHOULDER,
        fps=30.0,
    )
    ctx = PipelineCtx(
        pose_result=pose,
        phases=phases,
        features={
            "spine_angle_setup": 30.0,
            "finish_balance": 0.01,
            "wrist_release_timing": 0.3,
            "spine_angle_impact_delta": 20.0,
            "head_lateral_shift": 0.15,
            "x_factor": 70.0,
        },
        quality_warnings=[],
        fps=30.0,
    )
    result = AnalyzeResult(
        analysis_id="smoke",
        status="completed",
        overall_score=70,
        issues=[
            IssueItem(type="early_extension", name="x", severity="medium", description="x"),
            IssueItem(type="casting", name="x", severity="medium", description="x"),
            IssueItem(type="sway_slide", name="x", severity="medium", description="x"),
            IssueItem(type="flat_shoulder", name="x", severity="medium", description="x"),
        ],
        recommendations=[],
    )
    _enrich_v2(result, ctx)

    print("feature_confidences:")
    for k, v in sorted(result.feature_confidences.items()):
        print(f"  {k:30s}  {v}")
    print(f"analysis_confidence: {result.analysis_confidence}")
    for i in result.issues:
        print(f"issue {i.type:20s}  conf={i.confidence}  tier={i.confidence_tier}")


if __name__ == "__main__":
    main()
