"""effective_minio_public_endpoint：staging/prod 占位回退."""

from __future__ import annotations

from app.config import Settings


def test_prod_derives_placeholder_to_api_minio() -> None:
    s = Settings(
        APP_ENV="prod",
        STORAGE_PROVIDER="minio",
        MINIO_PUBLIC_ENDPOINT="http://localhost:9000",
        API_PUBLIC_BASE_URL="https://api.birdieai.cn",
    )
    assert s.effective_minio_public_endpoint == "https://api.birdieai.cn/minio"


def test_local_does_not_derive() -> None:
    s = Settings(
        APP_ENV="local",
        STORAGE_PROVIDER="minio",
        MINIO_PUBLIC_ENDPOINT="http://localhost:9000",
        API_PUBLIC_BASE_URL="http://localhost:8000",
    )
    assert s.effective_minio_public_endpoint == "http://localhost:9000"


def test_explicit_public_preserved_under_prod() -> None:
    s = Settings(
        APP_ENV="prod",
        STORAGE_PROVIDER="minio",
        MINIO_PUBLIC_ENDPOINT="https://upload.example.com/minio",
        API_PUBLIC_BASE_URL="https://api.example.com",
    )
    assert s.effective_minio_public_endpoint == "https://upload.example.com/minio"


def test_https_localhost_api_does_not_derive() -> None:
    """避免误判含 localhost 的假 https。"""
    s = Settings(
        APP_ENV="prod",
        STORAGE_PROVIDER="minio",
        MINIO_PUBLIC_ENDPOINT="http://localhost:9000",
        API_PUBLIC_BASE_URL="https://localhost:8443",
    )
    assert s.effective_minio_public_endpoint == "http://localhost:9000"
