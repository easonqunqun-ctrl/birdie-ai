"""derive_skeleton：拒绝原片重转码；成功后删除 normalized。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.pipeline.derive_skeleton import run_derive_skeleton
from app.schemas import DeriveSkeletonRequest


@pytest.fixture()
def req() -> DeriveSkeletonRequest:
    return DeriveSkeletonRequest(
        analysis_id="ana_test_derive",
        normalized_video_url="https://example.com/b/normalized/ana_test_derive.mp4",
        skeleton_data_url="https://example.com/b/skeleton_data/ana_test_derive.parquet",
        video_url="https://example.com/b/original.mp4",
    )


def test_derive_fails_when_normalized_missing_no_repreprocess(req, monkeypatch) -> None:
    """归一化视频下不到时不得调用 preprocess_video（防帧错位）。"""
    called = {"preprocess": False}

    def _boom(*_a, **_k):
        raise FileNotFoundError("normalized gone")

    def _no_preprocess(*_a, **_k):
        called["preprocess"] = True
        raise AssertionError("must not re-preprocess")

    monkeypatch.setattr("app.pipeline.derive_skeleton._download_url", _boom)
    monkeypatch.setattr(
        "app.pipeline.preprocess.preprocess_video",
        _no_preprocess,
        raising=False,
    )
    # 即便有人误 import preprocess，也不应走到
    import app.pipeline.derive_skeleton as mod

    assert not hasattr(mod, "preprocess_video")

    result = run_derive_skeleton(req)
    assert result.status == "failed"
    assert "归一化" in (result.error_message or "")
    assert called["preprocess"] is False


def test_derive_success_deletes_normalized(req, monkeypatch, tmp_path) -> None:
    storage = MagicMock()
    storage.build_public_url.side_effect = lambda key: f"https://example.com/b/{key}"
    storage.put_file.return_value = "https://example.com/b/skeleton/ana_test_derive.mp4"
    storage.delete_object.return_value = True
    monkeypatch.setattr("app.pipeline.derive_skeleton.get_storage", lambda: storage)

    pose = MagicMock()
    pose.num_frames = 10

    def _fake_download(url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * 64)
        return dest

    monkeypatch.setattr("app.pipeline.derive_skeleton._download_url", _fake_download)
    monkeypatch.setattr(
        "app.pipeline.derive_skeleton.load_pose_from_parquet", lambda *_a, **_k: pose
    )
    monkeypatch.setattr(
        "app.pipeline.derive_skeleton.render_skeleton_video",
        lambda *_a, **_k: tmp_path / "out.mp4",
    )
    (tmp_path / "out.mp4").write_bytes(b"mp4")

    result = run_derive_skeleton(req)
    assert result.status == "completed"
    assert result.skeleton_video_url.endswith(".mp4")
    storage.delete_object.assert_called_once()
    assert "normalized/" in storage.delete_object.call_args[0][0]
