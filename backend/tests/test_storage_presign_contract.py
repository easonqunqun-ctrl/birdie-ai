"""COS / MinIO：`storage_presign_origin_base` 主机推导（不测真上传、不连外网）."""

from __future__ import annotations

from app.config import Settings


def test_cos_presign_defaults_to_regional_myqcloud_when_public_base_empty():
    s = Settings(
        STORAGE_PROVIDER="cos",
        COS_REGION="ap-shanghai",
        COS_BUCKET="buck-1250000000",
        COS_PUBLIC_BASE="",
    )
    assert "myqcloud.com" in s.storage_presign_origin_base


def test_cos_presign_respects_explicit_public_base():
    s = Settings(
        STORAGE_PROVIDER="cos",
        COS_REGION="ap-shanghai",
        COS_BUCKET="b",
        COS_PUBLIC_BASE="https://videos.example.com/",
    )
    assert s.storage_presign_origin_base.rstrip("/") == "https://videos.example.com"
