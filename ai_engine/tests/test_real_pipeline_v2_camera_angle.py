"""P2-W12-2 · `_enrich_v2` 接入 camera_angle 检测的单测.

W7 时 ``compute_analysis_confidence(camera_angle_offset_deg=None)``，相当于机位
独立标尺永远不惩罚 confidence。W12-2 真正接入：``_summarize_pose_for_angle`` 从
PoseResult 抽 6 点几何摘要 → ``detect_camera_angle`` → ``offset_deg`` 喂
``compute_analysis_confidence``；同时 ``angle_engine_warnings`` 追加进 result.

本测覆盖：
- 正机位（face_on，offset_deg≈0）confidence 不受惩罚
- 大偏角（>15°）confidence 触发 ``ANGLE_PENALTY_BAD=0.6`` 且出现
  ``camera_angle_large_offset`` warning
- 无有效帧 / pose 为空 → 跳过 angle 注入不抛错
- run_real_analysis_v2 末尾把 probe / angle / fallback warnings **合并**而非覆盖
"""

from __future__ import annotations

import numpy as np
import pytest

from app.pipeline.confidence import ANGLE_HARD_OFFSET_DEG, ANGLE_PENALTY_BAD
from app.pipeline.phases import PhaseInfo, PhaseSegmentResult
from app.pipeline.pose import (
    LANDMARK_LEFT_HIP,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_NOSE,
    LANDMARK_RIGHT_HIP,
    LANDMARK_RIGHT_SHOULDER,
    PoseResult,
)
from app.pipeline.real_pipeline import PipelineCtx
from app.pipeline.real_pipeline_v2 import (
    _enrich_v2,
    _maybe_detect_angle,
    _summarize_pose_for_angle,
    reset_caches,
)
from app.schemas import AnalyzeResult, IssueItem


def _make_ctx_with_declared(
    pose: PoseResult,
    *,
    declared: str | None = None,
    features: dict[str, float] | None = None,
) -> PipelineCtx:
    """W13-B 单测 helper：构造带 declared_camera_angle 的 PipelineCtx."""
    return PipelineCtx(
        pose_result=pose,
        phases=_make_phases(),
        features=features or {"wrist_release_timing": 0.30},
        quality_warnings=[],
        fps=30.0,
        declared_camera_angle=declared,
    )


@pytest.fixture(autouse=True)
def _reset():
    reset_caches()


def _make_pose_with_shoulder_width(
    *,
    shoulder_width: float,
    mean_vis: float = 0.9,
    num_frames: int = 30,
    hip_width: float | None = None,
) -> PoseResult:
    """构造 keypoints 让左右肩 / 髋 / 鼻位于指定 x 坐标，触发 camera_angle 检测.

    Args:
        shoulder_width: 左右肩 x 距离（MediaPipe 归一化坐标 [0,1]）
        hip_width: 默认与 shoulder_width 一致（width_consistency=1）
    """
    if hip_width is None:
        hip_width = shoulder_width
    kp = np.zeros((num_frames, 33, 3), dtype=np.float32)
    # 把人放在画面中央
    left_x = 0.5 + shoulder_width / 2
    right_x = 0.5 - shoulder_width / 2
    kp[:, LANDMARK_LEFT_SHOULDER, 0] = left_x
    kp[:, LANDMARK_RIGHT_SHOULDER, 0] = right_x
    kp[:, LANDMARK_LEFT_HIP, 0] = 0.5 + hip_width / 2
    kp[:, LANDMARK_RIGHT_HIP, 0] = 0.5 - hip_width / 2
    kp[:, LANDMARK_NOSE, 0] = 0.5
    kp[:, LANDMARK_NOSE, 1] = 0.2
    vis = np.full((num_frames, 33), mean_vis, dtype=np.float32)
    return PoseResult(
        keypoints=kp,
        visibility=vis,
        valid_mask=np.ones(num_frames, dtype=bool),
        num_frames=num_frames,
        fps=30.0,
    )


def _make_phases() -> PhaseSegmentResult:
    return PhaseSegmentResult(
        phases={
            "setup": PhaseInfo(start_frame=0, end_frame=4, key_frame=2),
            "backswing": PhaseInfo(start_frame=5, end_frame=14, key_frame=10),
            "top": PhaseInfo(start_frame=15, end_frame=15, key_frame=15),
            "downswing": PhaseInfo(start_frame=16, end_frame=19, key_frame=18),
            "impact": PhaseInfo(start_frame=20, end_frame=20, key_frame=20),
            "follow_through": PhaseInfo(start_frame=21, end_frame=29, key_frame=25),
        },
        top_frame=15,
        impact_frame=20,
        swing_start=5,
        swing_end=20,
        handedness="right",
        lead_wrist_idx=15,
        lead_shoulder_idx=11,
        fps=30.0,
    )


def _make_result() -> AnalyzeResult:
    return AnalyzeResult(
        analysis_id="w12_test",
        status="completed",
        overall_score=70,
        issues=[
            IssueItem(type="casting", name="casting", severity="medium", description="x"),
        ],
        recommendations=[],
    )


# ---------- _summarize_pose_for_angle / _maybe_detect_angle ----------


def test_summarize_pose_returns_none_for_empty_pose():
    empty = PoseResult(
        keypoints=np.zeros((0, 33, 3), dtype=np.float32),
        visibility=np.zeros((0, 33), dtype=np.float32),
        valid_mask=np.zeros(0, dtype=bool),
        num_frames=0,
        fps=30.0,
    )
    assert _summarize_pose_for_angle(empty) is None


def test_summarize_pose_returns_none_when_no_valid_frames():
    pose = PoseResult(
        keypoints=np.zeros((30, 33, 3), dtype=np.float32),
        visibility=np.zeros((30, 33), dtype=np.float32),
        valid_mask=np.zeros(30, dtype=bool),
        num_frames=30,
        fps=30.0,
    )
    assert _summarize_pose_for_angle(pose) is None


def test_maybe_detect_angle_face_on_returns_low_offset():
    """标准 face_on 肩宽 0.25 → offset_deg≈0."""
    pose = _make_pose_with_shoulder_width(shoulder_width=0.25)
    result = _maybe_detect_angle(pose)
    assert result is not None
    assert result.detected_angle == "face_on"
    assert result.offset_deg < 1.0  # 标准肩宽，offset≈0


def test_maybe_detect_angle_dtl_view_returns_dtl():
    """侧身 dtl 肩宽 ~0.05 → detected=down_the_line, offset_deg 较小."""
    pose = _make_pose_with_shoulder_width(shoulder_width=0.05)
    result = _maybe_detect_angle(pose)
    assert result is not None
    assert result.detected_angle == "down_the_line"


# ---------- _enrich_v2 正常 / 偏角大 ----------


def test_enrich_v2_face_on_does_not_penalize_confidence():
    """正机位 → angle_penalty=1.0；confidence 与 W7/W9 公式相比不应被惩罚."""
    pose = _make_pose_with_shoulder_width(shoulder_width=0.25, mean_vis=0.9)
    ctx = PipelineCtx(
        pose_result=pose,
        phases=_make_phases(),
        features={"wrist_release_timing": 0.30},
        quality_warnings=[],
        fps=30.0,
    )
    result = _make_result()
    _enrich_v2(result, ctx)
    # base=0.9, qw=1.0, angle=1.0, feat=0.9 → 0.81
    assert result.analysis_confidence == pytest.approx(0.81, abs=1e-3)
    # 正机位不应出现 camera_angle_large_offset
    codes = {w["code"] for w in (result.engine_warnings or [])}
    assert "camera_angle_large_offset" not in codes


def test_enrich_v2_large_offset_triggers_angle_penalty_and_warning():
    """oblique 介中（shoulder_width=0.12）→ offset>15° → angle_penalty=0.6 + warning.

    shoulder_width=0.12 落在 face_on (>=0.18) 与 dtl (<=0.09) 之间 → oblique，
    offset = min(|0.12-0.25|/0.25*45, |0.12-0.06|/0.06*30) = min(23.4, 30) = 23.4°
    > ANGLE_HARD_OFFSET_DEG(15.0) → angle_penalty = ANGLE_PENALTY_BAD(0.6)
    """
    pose = _make_pose_with_shoulder_width(shoulder_width=0.12, mean_vis=0.9)
    ctx = PipelineCtx(
        pose_result=pose,
        phases=_make_phases(),
        features={"wrist_release_timing": 0.30},
        quality_warnings=[],
        fps=30.0,
    )
    result = _make_result()
    _enrich_v2(result, ctx)
    # base=0.9, qw=1.0, angle=0.6 (W12-2 接入后), feat=0.9 → 0.486
    expected = round(0.9 * 1.0 * ANGLE_PENALTY_BAD * 0.9, 3)
    assert result.analysis_confidence == pytest.approx(expected, abs=1e-3)
    # 应出现 camera_angle_large_offset warning
    codes = {w["code"] for w in (result.engine_warnings or [])}
    assert "camera_angle_large_offset" in codes


def test_enrich_v2_empty_pose_skips_angle_injection_no_crash():
    """无 valid 帧 pose → _maybe_detect_angle 返 None → camera_offset=None.

    W7 行为：analysis_confidence 落 0（mean_vis=0）。W12-2 不能让 angle 注入
    破坏这个行为。
    """
    empty = PoseResult(
        keypoints=np.zeros((0, 33, 3), dtype=np.float32),
        visibility=np.zeros((0, 33), dtype=np.float32),
        valid_mask=np.zeros(0, dtype=bool),
        num_frames=0,
        fps=30.0,
    )
    ctx = PipelineCtx(
        pose_result=empty,
        phases=_make_phases(),
        features={"wrist_release_timing": 0.30},
        quality_warnings=[],
        fps=30.0,
    )
    result = _make_result()
    _enrich_v2(result, ctx)
    assert result.analysis_confidence == 0.0
    # 不抛 + 不写 angle warnings
    codes = {w["code"] for w in (result.engine_warnings or [])}
    assert "camera_angle_large_offset" not in codes


# ---------- engine_warnings 合并而非覆盖 ----------


# ============================================================
# P2-W13-B · attach_declared 接入 (camera_angle_mismatch warning)
# ============================================================


def test_pipeline_ctx_default_declared_is_none():
    """PipelineCtx 新增字段必须**向后兼容**：旧调用方不传也能构造（默认 None）."""
    pose = _make_pose_with_shoulder_width(shoulder_width=0.25)
    ctx = PipelineCtx(
        pose_result=pose,
        phases=_make_phases(),
        features={},
        quality_warnings=[],
        fps=30.0,
    )
    assert ctx.declared_camera_angle is None


def test_maybe_detect_angle_with_declared_face_on_matches_face_on_no_mismatch():
    """W13-B：declared=face_on + detected=face_on → mismatch=False（无 warning）."""
    pose = _make_pose_with_shoulder_width(shoulder_width=0.25)
    result = _maybe_detect_angle(pose, declared_camera_angle="face_on")
    assert result is not None
    assert result.declared_angle == "face_on"
    assert result.detected_angle == "face_on"
    assert result.mismatch is False


def test_maybe_detect_angle_with_mismatched_declared_triggers_mismatch():
    """W13-B：declared=down_the_line 但 detected=face_on (高置信) → mismatch=True."""
    # shoulder_width=0.25 + hip_width=0.25 → detected=face_on, conf ≈ 0.7+ (一致性奖励)
    pose = _make_pose_with_shoulder_width(shoulder_width=0.25)
    result = _maybe_detect_angle(pose, declared_camera_angle="down_the_line")
    assert result is not None
    assert result.declared_angle == "down_the_line"
    assert result.detected_angle == "face_on"
    assert result.mismatch is True


def test_maybe_detect_angle_with_invalid_declared_alias_does_not_crash():
    """W13-B：declared 是未知别名（前端传脏数据）→ attach_declared 抛 ValueError，
    但 _maybe_detect_angle 应吞掉并返回不带 mismatch 的 result（不阻塞主流程）."""
    pose = _make_pose_with_shoulder_width(shoulder_width=0.25)
    result = _maybe_detect_angle(pose, declared_camera_angle="nonsense_angle_value")
    assert result is not None
    assert result.declared_angle is None  # attach_declared 失败 → 走原 result（无 declared）
    assert result.mismatch is False


def test_enrich_v2_with_declared_mismatch_emits_camera_angle_mismatch_warning():
    """W13-B 端到端：ctx 带 declared=down_the_line + detected=face_on
    → result.engine_warnings 含 camera_angle_mismatch."""
    pose = _make_pose_with_shoulder_width(shoulder_width=0.25, mean_vis=0.9)
    ctx = _make_ctx_with_declared(pose, declared="down_the_line")
    result = _make_result()
    _enrich_v2(result, ctx)
    codes = {w["code"] for w in (result.engine_warnings or [])}
    assert "camera_angle_mismatch" in codes
    # 正机位（offset=0）所以**不应**同时触发 large_offset
    assert "camera_angle_large_offset" not in codes


def test_enrich_v2_without_declared_does_not_emit_mismatch_warning():
    """W13-B：ctx.declared_camera_angle=None → 不调 attach_declared，
    mismatch warning 永远不出现（向后兼容 W12-2 行为）."""
    pose = _make_pose_with_shoulder_width(shoulder_width=0.25, mean_vis=0.9)
    ctx = _make_ctx_with_declared(pose, declared=None)
    result = _make_result()
    _enrich_v2(result, ctx)
    codes = {w["code"] for w in (result.engine_warnings or [])}
    assert "camera_angle_mismatch" not in codes


def test_run_real_analysis_v2_merges_probe_and_angle_warnings(monkeypatch):
    """run_real_analysis_v2 末尾 angle warnings 不应被 probe / fallback 覆盖.

    模拟 _enrich_v2 在 result 上已经写了 angle warning + run_real_analysis_v2 末尾
    合并 probe warnings → 两者都应在最终 result.engine_warnings 里。
    """
    from app.pipeline import real_pipeline_v2 as v2

    # 1) 模拟 probe 返回一条 decoded_h264
    monkeypatch.setattr(
        v2,
        "_probe_video_warnings",
        lambda url: [v2.EngineWarning(code="decoded_h264", level="info", detail="codec=h264")],
    )

    # 2) 模拟 run_real_analysis 返回一个已经被 enrich 注入了 angle warning 的 result
    async def fake_run(req, *, diagnose_fn, enrichment_fn, club_aware_scoring=False):  # noqa: ARG001
        return AnalyzeResult(
            analysis_id=req.analysis_id,
            status="completed",
            overall_score=70,
            engine_warnings=[
                {
                    "code": "camera_angle_large_offset",
                    "level": "warn",
                    "detail": "offset_deg=23.4",
                }
            ],
        )

    import app.pipeline.real_pipeline as rp

    monkeypatch.setattr(rp, "run_real_analysis", fake_run)
    monkeypatch.setattr(v2, "run_real_analysis", fake_run, raising=False)
    # v2 内部 import 是 `from app.pipeline.real_pipeline import run_real_analysis`
    # 所以要 patch v2.run_real_analysis（rebind 已 import 的局部名）
    # 但其实 v2.run_real_analysis_v2 内部是 `from app.pipeline.real_pipeline import run_real_analysis`
    # 是函数内 import，每次都拿到 rp.run_real_analysis；上面 monkeypatch.setattr(rp,...) 已生效。

    import asyncio

    from app.schemas import AnalyzeRequest

    req = AnalyzeRequest(
        analysis_id="merge_test",
        video_url="https://x/v.mp4",
        camera_angle="face_on",
        club_type="iron_7",
    )
    result = asyncio.run(v2.run_real_analysis_v2(req))

    codes = {w["code"] for w in (result.engine_warnings or [])}
    # 必须同时含 angle warning（来自 fake enrich）+ probe warning（来自合并）
    assert "camera_angle_large_offset" in codes, "angle warning 被合并丢掉了"
    assert "decoded_h264" in codes, "probe warning 没合并进来"
