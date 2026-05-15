"""video_url/skeleton_video_url 同源改写：解决小程序 <Video> 对 /minio 路径黑屏。"""

from __future__ import annotations

import app.services.analysis_service as svc
from app.config import Settings


def test_to_proxy_video_url_rewrites_uploads(monkeypatch) -> None:
    s = Settings(
        APP_ENV="prod",
        STORAGE_PROVIDER="minio",
        MINIO_PUBLIC_ENDPOINT="https://api.example.com/minio",
        API_PUBLIC_BASE_URL="https://api.example.com",
        MINIO_BUCKET="bkt",
    )
    monkeypatch.setattr(svc, "settings", s)
    raw = "https://api.example.com/minio/bkt/uploads/2026/05/13/u/up.mp4"
    assert svc.to_proxy_video_url(raw) == (
        "https://api.example.com/v1/assets/video/uploads/2026/05/13/u/up.mp4"
    )


def test_to_proxy_video_url_rewrites_skeleton(monkeypatch) -> None:
    s = Settings(
        APP_ENV="prod",
        STORAGE_PROVIDER="minio",
        MINIO_PUBLIC_ENDPOINT="https://api.example.com/minio",
        API_PUBLIC_BASE_URL="https://api.example.com",
        MINIO_BUCKET="bkt",
    )
    monkeypatch.setattr(svc, "settings", s)
    raw = "https://api.example.com/minio/bkt/skeleton/ana_xyz.mp4"
    assert svc.to_proxy_video_url(raw) == (
        "https://api.example.com/v1/assets/video/skeleton/ana_xyz.mp4"
    )


def test_to_proxy_video_url_leaves_non_minio_unchanged(monkeypatch) -> None:
    s = Settings(
        APP_ENV="prod",
        STORAGE_PROVIDER="minio",
        MINIO_PUBLIC_ENDPOINT="https://api.example.com/minio",
        API_PUBLIC_BASE_URL="https://api.example.com",
        MINIO_BUCKET="bkt",
    )
    monkeypatch.setattr(svc, "settings", s)
    ext = "https://cdn.other.com/demo.mp4"
    assert svc.to_proxy_video_url(ext) == ext


def test_to_proxy_video_url_rewrites_when_db_has_internal_minio_host(monkeypatch) -> None:
    """骨架视频常见：AI 引擎用 MINIO_ENDPOINT/未回落的 PUBLIC 写出了 docker 内网 URL。"""
    s = Settings(
        APP_ENV="staging",
        STORAGE_PROVIDER="minio",
        MINIO_ENDPOINT="http://minio:9000",
        MINIO_PUBLIC_ENDPOINT="http://minio:9000",
        API_PUBLIC_BASE_URL="https://api.example.com",
        MINIO_BUCKET="bkt",
    )
    monkeypatch.setattr(svc, "settings", s)
    raw = "http://minio:9000/bkt/skeleton/ana_bad.mp4"
    assert svc.to_proxy_video_url(raw) == (
        "https://api.example.com/v1/assets/video/skeleton/ana_bad.mp4"
    )


def test_parse_video_range_suffix_and_open_ended():
    from app.api.v1 import assets as a

    assert a._parse_single_range("-10", size=100) == (90, 99)
    assert a._parse_single_range("50-", size=100) == (50, 99)
