"""异步补渲染骨骼叠加视频（主 /analyze 已 defer 时由 Celery 调用）。"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from app.config import settings
from app.pipeline.preprocess import (
    _prefer_internal_minio_download_url,
    preprocess_video,
)
from app.pipeline.visualize import (
    DEFAULT_SKELETON_OUTPUT_FPS,
    load_pose_from_parquet,
    make_artifacts_tmpdir,
    render_skeleton_video,
)
from app.schemas import DeriveSkeletonRequest, DeriveSkeletonResult
from app.storage import get_storage

log = logging.getLogger("ai_engine.derive_skeleton")


def _download_url(url: str, dest: Path) -> Path:
    """下载任意对象到指定路径（不复用 materialize 的 source.mp4 约定）。"""
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        fetch = _prefer_internal_minio_download_url(url)
        subprocess.run(
            ["curl", "-fsSL", "--max-time", "60", "-o", str(dest), fetch],
            check=True,
            capture_output=True,
            timeout=90,
        )
        return dest
    local = Path(url)
    if not local.exists():
        raise FileNotFoundError(url)
    shutil.copy2(local, dest)
    return dest


def run_derive_skeleton(req: DeriveSkeletonRequest) -> DeriveSkeletonResult:
    """用已上传的归一化视频 + pose parquet 渲染骨骼 mp4。"""
    t0 = time.perf_counter()
    storage = get_storage()
    work_dir = Path(tempfile.mkdtemp(prefix="ai_engine_derive_skel_"))
    tmpdir = make_artifacts_tmpdir(prefix="ai_engine_derive_out_")
    try:
        normalized_url = req.normalized_video_url or storage.build_public_url(
            f"{settings.DERIVED_NORMALIZED_PREFIX}/{req.analysis_id}.mp4"
        )
        parquet_url = req.skeleton_data_url or storage.build_public_url(
            f"{settings.DERIVED_POSE_DATA_PREFIX}/{req.analysis_id}.parquet"
        )

        normalized_path = work_dir / "normalized.mp4"
        try:
            _download_url(normalized_url, normalized_path)
        except Exception as exc:  # noqa: BLE001
            if not req.video_url:
                return DeriveSkeletonResult(
                    analysis_id=req.analysis_id,
                    status="failed",
                    error_message=f"归一化视频不可用: {exc}",
                    elapsed_ms=int((time.perf_counter() - t0) * 1000),
                )
            log.warning(
                "derive_skeleton_normalized_fallback",
                extra={"analysis_id": req.analysis_id, "err": repr(exc)},
            )
            pre = preprocess_video(req.video_url, work_dir=work_dir / "re_pre")
            normalized_path = Path(pre.normalized_video_path)

        parquet_local = work_dir / "pose.parquet"
        try:
            _download_url(parquet_url, parquet_local)
        except Exception as exc:  # noqa: BLE001
            return DeriveSkeletonResult(
                analysis_id=req.analysis_id,
                status="failed",
                error_message=f"pose parquet 下载失败: {exc}",
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
            )

        pose = load_pose_from_parquet(
            parquet_local, fps=DEFAULT_SKELETON_OUTPUT_FPS
        )
        if pose is None:
            return DeriveSkeletonResult(
                analysis_id=req.analysis_id,
                status="failed",
                error_message="无法从 parquet 还原姿态",
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
            )

        out_path = tmpdir / "skeleton.mp4"
        rendered = render_skeleton_video(normalized_path, pose, out_path)
        if rendered is None:
            return DeriveSkeletonResult(
                analysis_id=req.analysis_id,
                status="failed",
                error_message="骨骼视频编码失败",
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
            )

        key = f"{settings.DERIVED_SKELETON_PREFIX}/{req.analysis_id}.mp4"
        url = storage.put_file(rendered, key, content_type="video/mp4")
        if not url:
            return DeriveSkeletonResult(
                analysis_id=req.analysis_id,
                status="failed",
                error_message="骨骼视频上传失败",
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
            )

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        log.info(
            "derive_skeleton_done",
            extra={
                "analysis_id": req.analysis_id,
                "skeleton_video_url": url,
                "elapsed_ms": elapsed_ms,
            },
        )
        return DeriveSkeletonResult(
            analysis_id=req.analysis_id,
            status="completed",
            skeleton_video_url=url,
            elapsed_ms=elapsed_ms,
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        shutil.rmtree(tmpdir, ignore_errors=True)
