"""W6-T3：MinIO 上传客户端单元测试。

- enabled=False 路径：put_file 返回 None（disabled 退化）
- enabled=True 路径：mock 掉 minio.Minio，验证调用参数 + URL 构造
- 文件不存在 / 空文件：返回 None 不抛错
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.storage import DerivedAssetsStorage, get_storage, reset_storage_for_tests


@pytest.fixture(autouse=True)
def _reset_storage_singleton():
    reset_storage_for_tests()
    yield
    reset_storage_for_tests()


def test_put_file_disabled_returns_none(tmp_path: Path) -> None:
    storage = DerivedAssetsStorage(enabled=False)
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello")
    assert storage.put_file(f, "skeleton/abc.mp4") is None


def test_put_file_skips_missing_or_empty(tmp_path: Path) -> None:
    storage = DerivedAssetsStorage(enabled=False)  # disabled 也走前置校验
    storage.enabled = True
    storage._client = MagicMock()  # type: ignore[attr-defined]

    # 文件不存在
    assert storage.put_file(tmp_path / "nope.bin", "k1") is None
    storage._client.fput_object.assert_not_called()

    # 空文件
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    assert storage.put_file(empty, "k2") is None
    storage._client.fput_object.assert_not_called()


def test_put_file_uploads_and_returns_url(tmp_path: Path) -> None:
    storage = DerivedAssetsStorage(
        enabled=True,
        public_endpoint="http://localhost:9000",
        bucket="test-bucket",
    )
    storage._client = MagicMock()  # type: ignore[attr-defined]

    f = tmp_path / "blob.bin"
    f.write_bytes(b"hello world")
    url = storage.put_file(f, "skeleton/abc.mp4", content_type="video/mp4")
    assert url == "http://localhost:9000/test-bucket/skeleton/abc.mp4"
    storage._client.fput_object.assert_called_once()
    args, kwargs = storage._client.fput_object.call_args
    assert args[0] == "test-bucket"
    assert args[1] == "skeleton/abc.mp4"
    assert args[2] == str(f)
    assert kwargs.get("content_type") == "video/mp4"


def test_put_file_returns_none_on_s3_error(tmp_path: Path) -> None:
    from minio.error import S3Error

    storage = DerivedAssetsStorage(enabled=True)
    storage._client = MagicMock()  # type: ignore[attr-defined]
    storage._client.fput_object.side_effect = S3Error(
        "NoSuchBucket", "no such bucket", "k", "rid", "host", "resp"
    )

    f = tmp_path / "x.bin"
    f.write_bytes(b"x")
    assert storage.put_file(f, "k") is None


def test_build_public_url_strips_trailing_slash() -> None:
    s = DerivedAssetsStorage(enabled=False, public_endpoint="http://localhost:9000/", bucket="b")
    assert s.build_public_url("a/b.mp4") == "http://localhost:9000/b/a/b.mp4"


def test_get_storage_is_singleton() -> None:
    s1 = get_storage()
    s2 = get_storage()
    assert s1 is s2
