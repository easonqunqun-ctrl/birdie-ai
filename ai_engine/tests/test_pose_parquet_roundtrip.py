"""pose parquet dump/load 往返，供异步骨骼渲染。"""

from __future__ import annotations

import numpy as np

from app.pipeline.pose import PoseResult
from app.pipeline.visualize import dump_pose_parquet, load_pose_from_parquet


def test_pose_parquet_roundtrip(tmp_path) -> None:
    num_frames = 12
    keypoints = np.random.rand(num_frames, 33, 3).astype(np.float32)
    visibility = np.clip(np.random.rand(num_frames, 33), 0.2, 1.0).astype(np.float32)
    valid = np.ones(num_frames, dtype=bool)
    valid[0] = False
    pose = PoseResult(
        keypoints=keypoints,
        visibility=visibility,
        valid_mask=valid,
        num_frames=num_frames,
        fps=30.0,
    )
    path = dump_pose_parquet(pose, tmp_path / "pose.parquet")
    assert path is not None and path.exists()

    loaded = load_pose_from_parquet(path, fps=30.0)
    assert loaded is not None
    assert loaded.num_frames == num_frames
    assert loaded.fps == 30.0
    np.testing.assert_allclose(loaded.keypoints, keypoints, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(loaded.visibility, visibility, rtol=1e-5, atol=1e-5)
    np.testing.assert_array_equal(loaded.valid_mask, valid)
