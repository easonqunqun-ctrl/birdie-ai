"""P2-M7-13 · swing candidate preview 抽帧单测."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.pipeline.multi_swing import SwingCandidate
from app.pipeline.swing_candidate_previews import build_swing_candidate_items


def test_build_swing_candidate_items_uploads_preview() -> None:
    raw = [
        SwingCandidate(
            start_frame=10,
            end_frame=50,
            is_practice=False,
            confidence=0.9,
            speed_peak=1.0,
            top_frame=30,
            impact_frame=40,
        ),
    ]
    fake_storage = MagicMock()
    fake_storage.put_file.return_value = "http://minio.local/bucket/keyframes/upl_1/swing_0.jpg"

    with (
        patch(
            "app.pipeline.swing_candidate_previews.extract_keyframe",
            return_value=Path("/tmp/swing_0.jpg"),
        ),
        patch("app.pipeline.swing_candidate_previews.get_storage", return_value=fake_storage),
        patch("app.pipeline.swing_candidate_previews.make_artifacts_tmpdir", return_value=Path("/tmp")),
    ):
        items = build_swing_candidate_items(
            analysis_id="upl_1",
            normalized_video_path="/videos/norm.mp4",
            raw=raw,
            fps=30.0,
        )

    assert len(items) == 1
    assert items[0].preview_frame_url == "http://minio.local/bucket/keyframes/upl_1/swing_0.jpg"
    assert items[0].start_time_sec == round(10 / 30, 2)
    fake_storage.put_file.assert_called_once()
