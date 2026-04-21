"""W6-T3：real_pipeline 衍生产物 + MinIO 上传端到端烟测。

跳开 mediapipe（容器外没装也能跑）：直接用 synthetic_pose_result + 任一合成视频
（bouncing_box.mp4 帧数 90，正好对得上 fixture），调用内部
`_produce_derived_assets`，验证三类产物 URL 都签出来。

MinIO 上传分两组：
- **enabled 路径（in-container）**：依赖 docker-compose 起的 minio；通过 storage 上传，
  断言返回的 URL 形如 `<public>/<bucket>/<key>`，并用 minio SDK 拉回来 stat 一遍校验存在
- **disabled 路径**：把 storage 强制 disable，断言走占位 URL fallback

如果 minio 服务不可达（CI 无 docker-compose 起），enabled 测试自动 skip。
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from urllib.parse import urlparse

import pytest

from app.config import settings
from app.pipeline.real_pipeline import _placeholder_suffix, _produce_derived_assets
from app.storage import DerivedAssetsStorage, get_storage, reset_storage_for_tests
from tests.conftest import HAS_CV2, HAS_FFMPEG, SYNTHETIC_DIR


@pytest.fixture(autouse=True)
def _reset_storage():
    reset_storage_for_tests()
    yield
    reset_storage_for_tests()


def _minio_reachable() -> bool:
    """探测 MinIO 内网 endpoint 是否可连接（避免无 docker-compose 时一路 fail）。"""
    parsed = urlparse(settings.MINIO_ENDPOINT)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 9000)
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


needs_cv2_ffmpeg = pytest.mark.skipif(
    not (HAS_CV2 and HAS_FFMPEG),
    reason="cv2 或 ffmpeg 缺失",
)


def _bouncing_box() -> Path | None:
    p = SYNTHETIC_DIR / "bouncing_box.mp4"
    return p if p.exists() else None


@needs_cv2_ffmpeg
def test_produce_derived_assets_disabled_storage_uses_placeholders(
    synthetic_pose_result, monkeypatch
) -> None:
    """禁用上传时：skeleton/thumb 走占位 URL，parquet/keyframe 直接 None。"""
    # 强制 storage 单例返回 disabled
    monkeypatch.setattr(
        "app.pipeline.real_pipeline.get_storage",
        lambda: DerivedAssetsStorage(enabled=False),
    )

    src = _bouncing_box()
    if src is None:
        pytest.skip("bouncing_box.mp4 缺失")

    skeleton, thumb, pose_data, kf_urls = _produce_derived_assets(
        analysis_id="test-disabled",
        normalized_video_path=src,
        pose_result=synthetic_pose_result,
        issues_raw=[],
        fallback_video_url="https://example.com/foo.mp4",
    )

    assert skeleton == _placeholder_suffix("https://example.com/foo.mp4", "_skeleton.mp4")
    assert thumb == _placeholder_suffix("https://example.com/foo.mp4", "_thumb.jpg")
    assert pose_data is None  # disabled 时没有 fallback
    assert kf_urls == {}


@needs_cv2_ffmpeg
@pytest.mark.skipif(
    not _minio_reachable(),
    reason="MinIO 服务不可达（仅在 docker-compose 全栈起来后才跑此 e2e）",
)
def test_produce_derived_assets_uploads_to_minio(synthetic_pose_result) -> None:
    src = _bouncing_box()
    if src is None:
        pytest.skip("bouncing_box.mp4 缺失")

    # 用一个 test-only 前缀防止污染主目录
    analysis_id = f"e2e-{os.getpid()}"

    storage = get_storage()
    if not storage.enabled or storage._client is None:  # type: ignore[attr-defined]
        pytest.skip("storage disabled by env")

    skeleton, thumb, pose_data, kf_urls = _produce_derived_assets(
        analysis_id=analysis_id,
        normalized_video_path=src,
        pose_result=synthetic_pose_result,
        issues_raw=[],
        fallback_video_url="https://example.com/foo.mp4",
    )

    # skeleton / thumb / parquet 三类都应该是真实 minio URL（bucket 在 endpoint 后）
    assert skeleton is not None and settings.MINIO_BUCKET in skeleton
    assert thumb is not None and settings.MINIO_BUCKET in thumb
    assert pose_data is not None and pose_data.endswith(".parquet")

    # 用 minio SDK 反查每个 key 都在 bucket 里
    for url, suffix in [
        (skeleton, ".mp4"),
        (thumb, ".jpg"),
        (pose_data, ".parquet"),
    ]:
        # url 形如 http://localhost:9000/<bucket>/<key>
        # 取 bucket 之后的 key
        marker = f"/{settings.MINIO_BUCKET}/"
        assert marker in url
        key = url.split(marker, 1)[1]
        stat = storage._client.stat_object(settings.MINIO_BUCKET, key)  # type: ignore[attr-defined]
        assert stat.size > 0
        assert key.endswith(suffix)
