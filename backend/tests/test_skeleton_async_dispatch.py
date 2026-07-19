"""骨骼异步：仅 skeleton_pending 时派发 Celery 任务。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tasks import analysis_tasks


@pytest.mark.asyncio
async def test_dispatch_skeleton_only_when_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    delayed: list[tuple] = []

    def _delay(aid, norm, data, video):
        delayed.append((aid, norm, data, video))

    monkeypatch.setattr(
        analysis_tasks.render_analysis_skeleton,
        "delay",
        _delay,
    )
    monkeypatch.setattr(
        analysis_tasks,
        "_mark_processing",
        AsyncMock(
            return_value={
                "user_id": "u1",
                "video_url": "https://x/v.mp4",
                "camera_angle": "face_on",
                "club_type": "iron_7",
                "analysis_mode": "full_swing",
                "selected_swing_index": None,
            }
        ),
    )
    monkeypatch.setattr(analysis_tasks, "_progress_stages_loop", AsyncMock())
    monkeypatch.setattr(analysis_tasks, "_mark_completed", AsyncMock())
    monkeypatch.setattr(analysis_tasks, "_mark_failed", AsyncMock())

    client = MagicMock()
    client.analyze = AsyncMock(
        return_value={
            "status": "completed",
            "overall_score": 70,
            "skeleton_pending": True,
            "normalized_video_url": "https://x/normalized/a1.mp4",
            "skeleton_data_url": "https://x/skeleton_data/a1.parquet",
            "skeleton_video_url": None,
        }
    )
    monkeypatch.setattr(analysis_tasks, "get_ai_engine", lambda: client)

    await analysis_tasks._run_swing_analysis_async("a1")
    assert len(delayed) == 1
    assert delayed[0][0] == "a1"
    assert delayed[0][1] == "https://x/normalized/a1.mp4"


@pytest.mark.asyncio
async def test_no_dispatch_without_skeleton_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    delayed: list = []
    monkeypatch.setattr(
        analysis_tasks.render_analysis_skeleton,
        "delay",
        lambda *a, **k: delayed.append(a),
    )
    monkeypatch.setattr(
        analysis_tasks,
        "_mark_processing",
        AsyncMock(
            return_value={
                "user_id": "u1",
                "video_url": "https://x/v.mp4",
                "camera_angle": "face_on",
                "club_type": "iron_7",
                "analysis_mode": "full_swing",
                "selected_swing_index": None,
            }
        ),
    )
    monkeypatch.setattr(analysis_tasks, "_progress_stages_loop", AsyncMock())
    monkeypatch.setattr(analysis_tasks, "_mark_completed", AsyncMock())

    client = MagicMock()
    # 旧行为宽条件：无 skeleton_url 但有 data_url —— 现在不应派发
    client.analyze = AsyncMock(
        return_value={
            "status": "completed",
            "overall_score": 70,
            "skeleton_pending": False,
            "skeleton_data_url": "https://x/skeleton_data/a1.parquet",
            "skeleton_video_url": None,
        }
    )
    monkeypatch.setattr(analysis_tasks, "get_ai_engine", lambda: client)

    await analysis_tasks._run_swing_analysis_async("a1")
    assert delayed == []
