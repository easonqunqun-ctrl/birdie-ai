"""P2-M7-R1-B7 · preprocess V1/V2 路由单测。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.pipeline.preprocess_router import (
    ENGINE_V2,
    preprocess_for_pipeline,
    should_use_preprocess_v2,
)


def test_should_use_preprocess_v2_false_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "M7_VIDEO_READER_V2_ENABLED", False)
    assert should_use_preprocess_v2(engine_version=ENGINE_V2) is False


def test_should_use_preprocess_v2_requires_v2_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "M7_VIDEO_READER_V2_ENABLED", True)
    assert should_use_preprocess_v2(engine_version="v1") is False
    assert should_use_preprocess_v2(engine_version=ENGINE_V2) is True


def test_preprocess_for_pipeline_v1_path() -> None:
    fake_pre = MagicMock(fps=30.0)
    with patch(
        "app.pipeline.preprocess_router.preprocess_video",
        return_value=fake_pre,
    ) as mock_v1:
        pre, warnings, reader = preprocess_for_pipeline("/x.mp4", use_v2=False)
    mock_v1.assert_called_once_with("/x.mp4")
    assert pre is fake_pre
    assert warnings == []
    assert reader == "v1"


def test_preprocess_for_pipeline_v2_path() -> None:
    fake_pre = MagicMock(fps=60.0, engine_warnings=[])
    with patch(
        "app.pipeline.preprocess_router.preprocess_video_v2",
        return_value=fake_pre,
    ) as mock_v2:
        pre, warnings, reader = preprocess_for_pipeline("/y.mp4", use_v2=True)
    mock_v2.assert_called_once_with("/y.mp4")
    assert pre is fake_pre
    assert reader == "v2"
    assert warnings == []
