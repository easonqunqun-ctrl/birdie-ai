"""Settings：对外 URL 衍生（小程序域名对齐）断言。"""
from __future__ import annotations

from app.config import Settings


def test_storage_presign_origin_cos_defaults() -> None:
    s = Settings(STORAGE_PROVIDER="cos", COS_REGION="ap-beijing")
    assert "https://cos.ap-beijing.myqcloud.com" == s.storage_presign_origin_base


def test_storage_presign_origin_cos_custom_public_base() -> None:
    s = Settings(
        STORAGE_PROVIDER="cos",
        COS_REGION="ap-shanghai",
        COS_PUBLIC_BASE="https://cdn.example.com/oss",
    )
    assert s.storage_presign_origin_base == "https://cdn.example.com/oss"


def test_effective_api_public_strips_spaces() -> None:
    s = Settings(API_PUBLIC_BASE_URL="  https://api.x  ")
    assert s.effective_api_public_base_url == "https://api.x"
