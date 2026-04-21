"""W6-T3：可视化产物（骨骼视频 / 关键帧 / parquet）单元测试。

策略：
- parquet：纯 numpy → pyarrow，最容易测，验证 schema + 文件大小
- 骨骼视频：依赖 cv2 + ffmpeg，没装就 skip；用合成 1s 视频做最小烟测
- 关键帧 JPG：依赖 cv2，用合成视频抽 1 帧
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.pipeline.diagnose import DiagnosedIssue
from app.pipeline.visualize import (
    dump_pose_parquet,
    extract_issue_keyframes,
    extract_keyframe,
    render_skeleton_video,
)
from tests.conftest import HAS_CV2, HAS_FFMPEG, needs_cv2, needs_ffmpeg


# ============================================================
# 工具：生成一个 30 帧 320x240 的纯色视频用于 OpenCV 读取测试
# ============================================================


def _make_solid_color_video(path: Path, *, width: int = 320, height: int = 240, frames: int = 30, fps: int = 30) -> bool:
    """用 ffmpeg 造一个纯色测试视频。失败返回 False（让测试 skip）。"""
    if not HAS_FFMPEG:
        return False
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi",
        "-i", f"color=c=gray:s={width}x{height}:r={fps}:d={frames / fps:.3f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(path),
    ]
    rc = subprocess.run(cmd, capture_output=True).returncode
    return rc == 0 and path.exists() and path.stat().st_size > 0


# ============================================================
# parquet
# ============================================================


def test_dump_pose_parquet_writes_correct_schema(synthetic_pose_result, tmp_path: Path) -> None:
    pq = pytest.importorskip("pyarrow.parquet")

    out = tmp_path / "pose.parquet"
    result = dump_pose_parquet(synthetic_pose_result, out)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0

    table = pq.read_table(out)
    cols = table.schema.names

    assert "frame_idx" in cols
    assert "valid" in cols
    for axis in ("x", "y", "z"):
        for i in range(33):
            assert f"kp_{axis}_{i}" in cols
    for i in range(33):
        assert f"vis_{i}" in cols

    assert table.num_rows == synthetic_pose_result.num_frames


def test_dump_pose_parquet_data_roundtrip(synthetic_pose_result, tmp_path: Path) -> None:
    pq = pytest.importorskip("pyarrow.parquet")

    out = tmp_path / "pose.parquet"
    dump_pose_parquet(synthetic_pose_result, out)
    table = pq.read_table(out).to_pydict()

    # 第 10 帧的 nose.x（landmark 0 in MediaPipe = nose）应该等于 setup_kp 写进去的 0.50
    assert table["kp_x_0"][10] == pytest.approx(0.50, abs=1e-4)
    assert table["frame_idx"][0] == 0
    assert table["frame_idx"][-1] == synthetic_pose_result.num_frames - 1
    assert table["valid"][0] is True


# ============================================================
# 骨骼视频
# ============================================================


@needs_cv2
@needs_ffmpeg
def test_render_skeleton_video_smoke(synthetic_pose_result, tmp_path: Path) -> None:
    src = tmp_path / "src.mp4"
    if not _make_solid_color_video(src, frames=synthetic_pose_result.num_frames):
        pytest.skip("无法用 ffmpeg 生成测试视频")

    out = tmp_path / "skeleton.mp4"
    result = render_skeleton_video(src, synthetic_pose_result, out)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 1000  # 至少 1KB，确保 ffmpeg 真的写了东西

    # 用 ffprobe 校验是 H.264
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1", str(out)],
        capture_output=True, text=True,
    )
    assert "h264" in probe.stdout.lower()


def test_render_skeleton_video_missing_input_returns_none(synthetic_pose_result, tmp_path: Path) -> None:
    result = render_skeleton_video(tmp_path / "nope.mp4", synthetic_pose_result, tmp_path / "out.mp4")
    assert result is None


# ============================================================
# 关键帧 JPG
# ============================================================


@needs_cv2
@needs_ffmpeg
def test_extract_keyframe_writes_jpg(synthetic_pose_result, tmp_path: Path) -> None:
    src = tmp_path / "src.mp4"
    if not _make_solid_color_video(src):
        pytest.skip("无法用 ffmpeg 生成测试视频")

    out = tmp_path / "kf.jpg"
    result = extract_keyframe(src, frame_idx=5, output_path=out, pose_result=synthetic_pose_result)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 100


def test_extract_keyframe_negative_idx_returns_none(synthetic_pose_result, tmp_path: Path) -> None:
    assert extract_keyframe(tmp_path / "x.mp4", -1, tmp_path / "k.jpg") is None


@needs_cv2
@needs_ffmpeg
def test_extract_issue_keyframes_for_each_issue(synthetic_pose_result, tmp_path: Path) -> None:
    src = tmp_path / "src.mp4"
    if not _make_solid_color_video(src):
        pytest.skip("无法用 ffmpeg 生成测试视频")

    issues = [
        DiagnosedIssue(
            type="casting",
            name="过早释放",
            severity="high",
            description="x",
            confidence=0.9,
            key_frame_timestamp=20 / 30.0,
        ),
        DiagnosedIssue(
            type="early_extension",
            name="抬身",
            severity="medium",
            description="y",
            confidence=0.7,
            key_frame_timestamp=22 / 30.0,
        ),
        # 这条没有 timestamp，应该被跳过
        DiagnosedIssue(
            type="no_ts",
            name="x",
            severity="low",
            description="z",
            confidence=0.6,
            key_frame_timestamp=None,
        ),
    ]

    out_dir = tmp_path / "kfs"
    paths = extract_issue_keyframes(src, issues, synthetic_pose_result, out_dir)

    assert "casting" in paths
    assert "early_extension" in paths
    assert "no_ts" not in paths
    for p in paths.values():
        assert p.exists()
        assert p.stat().st_size > 100


# ============================================================
# pyarrow 缺失分支
# ============================================================


def test_dump_pose_parquet_returns_none_when_pyarrow_missing(synthetic_pose_result, tmp_path: Path, monkeypatch) -> None:
    """模拟 pyarrow 不可用：确保走 try/except 分支返回 None 不抛错。"""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pyarrow" or name.startswith("pyarrow."):
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert dump_pose_parquet(synthetic_pose_result, tmp_path / "x.parquet") is None


# 个别 test 已经用 @needs_cv2 / @needs_ffmpeg 标记，这里不再统一 skip 全模块，
# 因为 parquet 测试不依赖 cv2/ffmpeg，可以独立跑通。
_ = HAS_CV2  # 引用避免 ruff F401
