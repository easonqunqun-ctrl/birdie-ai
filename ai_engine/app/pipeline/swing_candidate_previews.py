"""P2-M7-13 · 多挥候选缩略图：按段抽 impact 帧并上传 MinIO。"""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.pipeline.multi_swing import SwingCandidate
from app.pipeline.visualize import extract_keyframe, make_artifacts_tmpdir
from app.schemas import SwingCandidateItem
from app.storage import get_storage

log = logging.getLogger("ai_engine.swing_candidate_previews")


def build_swing_candidate_items(
    *,
    analysis_id: str,
    normalized_video_path: Path | str,
    raw: list[SwingCandidate],
    fps: float,
) -> list[SwingCandidateItem]:
    """把 SwingCandidate 转为 API DTO，并尽力附上 preview_frame_url。"""
    if not raw:
        return []

    storage = get_storage()
    tmpdir = make_artifacts_tmpdir(prefix="ai_engine_swing_prev_")
    items: list[SwingCandidateItem] = []

    for idx, candidate in enumerate(raw):
        preview_url: str | None = None
        frame_idx = candidate.impact_frame
        if frame_idx < candidate.start_frame or frame_idx > candidate.end_frame:
            frame_idx = (candidate.start_frame + candidate.end_frame) // 2

        thumb_path = extract_keyframe(
            normalized_video_path,
            frame_idx,
            tmpdir / f"swing_{idx}.jpg",
            overlay_pose=False,
        )
        if thumb_path is not None:
            key = f"{settings.DERIVED_KEYFRAME_PREFIX}/{analysis_id}/swing_{idx}.jpg"
            preview_url = storage.put_file(thumb_path, key, content_type="image/jpeg")
        else:
            log.warning(
                "swing_candidate_preview_failed",
                extra={"analysis_id": analysis_id, "index": idx, "frame_idx": frame_idx},
            )

        base = candidate.to_dict(fps)
        items.append(SwingCandidateItem(**base, preview_frame_url=preview_url))

    return items
