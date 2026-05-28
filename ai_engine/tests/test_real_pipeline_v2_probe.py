"""P2-W8 ENG-C · ``_probe_video_warnings`` + run_real_analysis_v2 合并 warnings 单测.

不依赖真实视频 / ffprobe：mock ``_ffprobe_extended`` 返回不同 ``_ProbeInfoExtended``
状态，验证 ``_probe_video_warnings`` 是否产出对应的 ``EngineWarning``，
且失败时静默返回空列表、不抛异常。
"""

from __future__ import annotations

import pytest

from app.pipeline import real_pipeline_v2 as rp2_mod
from app.pipeline.preprocess_v2 import _ProbeInfoExtended
from app.pipeline.real_pipeline_v2 import _probe_video_warnings


def _probe(
    *,
    codec: str = "h264",
    fps_raw: float = 30.0,
    pix_fmt: str = "yuv420p",
    color_transfer: str = "bt709",
    nominal_fps: float = 0.0,
    is_slowmo: bool = False,
    is_hdr: bool = False,
    is_10bit: bool = False,
    has_audio: bool = False,
) -> _ProbeInfoExtended:
    return _ProbeInfoExtended(
        duration_sec=5.0,
        width=720,
        height=1280,
        fps_raw=fps_raw,
        codec_name=codec,
        container_format_name="mov,mp4,m4a,3gp,3g2,mj2",
        pix_fmt=pix_fmt,
        color_space="bt709",
        color_transfer=color_transfer,
        color_primaries="bt709",
        has_audio=has_audio,
        nominal_fps=nominal_fps,
        is_slowmo=is_slowmo,
        is_hdr=is_hdr,
        is_10bit=is_10bit,
    )


# ---------- codec 类 ----------


def test_probe_h264_emits_decoded_h264(monkeypatch):
    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="h264"))
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    codes = {w.code for w in warnings}
    assert "decoded_h264" in codes
    assert "decoded_hevc" not in codes
    assert "decoded_vp9" not in codes


def test_probe_hevc_emits_decoded_hevc(monkeypatch):
    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="hevc"))
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    codes = {w.code for w in warnings}
    assert "decoded_hevc" in codes
    assert "decoded_h264" not in codes


def test_probe_h265_aliases_to_decoded_hevc(monkeypatch):
    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="h265"))
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    assert "decoded_hevc" in {w.code for w in warnings}


def test_probe_vp9_emits_decoded_vp9(monkeypatch):
    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="vp9"))
    warnings = _probe_video_warnings("https://example.com/v.webm")
    codes = {w.code for w in warnings}
    assert "decoded_vp9" in codes


def test_probe_unknown_codec_no_decoded_warning(monkeypatch):
    monkeypatch.setattr(
        rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="av1")
    )
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    codes = {w.code for w in warnings}
    assert not any(c.startswith("decoded_") for c in codes)


# ---------- HDR ----------


def test_probe_hdr_emits_hdr_tonemapped(monkeypatch):
    monkeypatch.setattr(
        rp2_mod,
        "_ffprobe_extended",
        lambda _: _probe(
            codec="hevc",
            color_transfer="smpte2084",
            pix_fmt="yuv420p10le",
            is_hdr=True,
            is_10bit=True,
        ),
    )
    warnings = _probe_video_warnings("https://example.com/v.mov")
    codes = [w.code for w in warnings]
    details = {w.code: w.detail for w in warnings}
    assert "hdr_tonemapped" in codes
    assert "smpte2084" in details["hdr_tonemapped"]
    assert "yuv420p10le" in details["hdr_tonemapped"]


def test_probe_sdr_no_hdr_warning(monkeypatch):
    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="h264"))
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    assert "hdr_tonemapped" not in {w.code for w in warnings}


# ---------- 慢动作 ----------


def test_probe_slowmo_emits_slowmo_and_nominal_fps(monkeypatch):
    monkeypatch.setattr(
        rp2_mod,
        "_ffprobe_extended",
        lambda _: _probe(
            codec="hevc",
            fps_raw=240.0,
            nominal_fps=30.0,
            is_slowmo=True,
        ),
    )
    warnings = _probe_video_warnings("https://example.com/v.mov")
    codes = {w.code for w in warnings}
    assert "slowmo_detected" in codes
    assert "nominal_fps_used" in codes


def test_probe_no_slowmo_no_warning(monkeypatch):
    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="h264"))
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    codes = {w.code for w in warnings}
    assert "slowmo_detected" not in codes
    assert "nominal_fps_used" not in codes


# ---------- fps ----------


def test_probe_fps_30_emits_downsampled_relative_to_v2_target_60(monkeypatch):
    """fps_raw=30 vs TARGET_FPS_V2=60 → fps_upsampled（30 < 60）."""
    monkeypatch.setattr(
        rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="h264", fps_raw=30.0)
    )
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    codes = {w.code for w in warnings}
    assert "fps_upsampled" in codes
    assert "fps_downsampled" not in codes


def test_probe_fps_120_emits_downsampled(monkeypatch):
    monkeypatch.setattr(
        rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="h264", fps_raw=120.0)
    )
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    codes = {w.code for w in warnings}
    assert "fps_downsampled" in codes


def test_probe_fps_60_no_fps_warning(monkeypatch):
    monkeypatch.setattr(
        rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="h264", fps_raw=60.0)
    )
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    codes = {w.code for w in warnings}
    assert "fps_upsampled" not in codes
    assert "fps_downsampled" not in codes


def test_probe_fps_zero_no_fps_warning(monkeypatch):
    """fps_raw=0（探测失败的边界）→ 不生成 fps 类 warning."""
    monkeypatch.setattr(
        rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="h264", fps_raw=0.0)
    )
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    codes = {w.code for w in warnings}
    assert "fps_upsampled" not in codes
    assert "fps_downsampled" not in codes


# ---------- audio ----------


def test_probe_audio_present_emits_audio_kept(monkeypatch):
    monkeypatch.setattr(
        rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="h264", has_audio=True)
    )
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    codes = {w.code for w in warnings}
    assert "audio_kept" in codes
    assert "audio_dropped" not in codes


def test_probe_no_audio_emits_audio_dropped(monkeypatch):
    monkeypatch.setattr(
        rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="h264", has_audio=False)
    )
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    codes = {w.code for w in warnings}
    assert "audio_dropped" in codes
    assert "audio_kept" not in codes


# ---------- 多 warning 组合 ----------


def test_probe_iphone_slowmo_hdr_combo(monkeypatch):
    """典型 iPhone 14 慢动作 HDR HEVC：5 类 warning 同时触发."""
    monkeypatch.setattr(
        rp2_mod,
        "_ffprobe_extended",
        lambda _: _probe(
            codec="hevc",
            fps_raw=240.0,
            nominal_fps=30.0,
            color_transfer="smpte2084",
            pix_fmt="yuv420p10le",
            is_slowmo=True,
            is_hdr=True,
            is_10bit=True,
            has_audio=True,
        ),
    )
    warnings = _probe_video_warnings("https://example.com/v.mov")
    codes = {w.code for w in warnings}
    assert codes >= {
        "decoded_hevc",
        "hdr_tonemapped",
        "slowmo_detected",
        "nominal_fps_used",
        "fps_downsampled",  # 240 > 60
        "audio_kept",
    }


# ---------- 失败鲁棒性 ----------


def test_probe_ffprobe_raises_emits_probe_failed_warning(monkeypatch, caplog):
    """W12-3 改变：ffprobe 抛非可重试异常 → 返回单条 ``probe_failed`` warning（之前 W8/W9 是返回 [] 静默）.

    rationale：客户端 W10 已经有「调试浮层」展示 engine_warnings；让 ``probe_failed``
    透传到那里，比静默吞掉信息更利于线上排查（用户也能截图反馈"调试浮层显示 5xx"）。
    """

    def _raise(_):
        raise RuntimeError("ffprobe binary not found / network unreachable")

    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", _raise)
    warnings = _probe_video_warnings("https://example.com/v.mp4")
    assert len(warnings) == 1
    assert warnings[0].code == "probe_failed"
    # reason 落 unknown（既不是 5xx / 4xx / timeout / binary_missing 关键字）
    assert "reason=unknown" in warnings[0].detail


def test_probe_empty_video_url_returns_empty():
    """空 URL → 直接 []，不调 ffprobe."""
    assert _probe_video_warnings("") == []


def test_probe_known_codes_are_in_KNOWN_CODES_enum():
    """所有产出的 code 必须在 engine_warnings.KNOWN_CODES 白名单内。"""
    from app.pipeline.engine_warnings import KNOWN_CODES

    produced = {
        "decoded_h264",
        "decoded_hevc",
        "decoded_vp9",
        "hdr_tonemapped",
        "slowmo_detected",
        "nominal_fps_used",
        "fps_upsampled",
        "fps_downsampled",
        "audio_kept",
        "audio_dropped",
    }
    missing = produced - KNOWN_CODES
    assert not missing, f"未注册到 KNOWN_CODES: {missing}"


# ---------- 集成：run_real_analysis_v2 合并 probe + fallback warnings ----------


def test_run_real_analysis_v2_merges_probe_warnings_into_result(monkeypatch):
    """run_real_analysis_v2 应把 probe warnings 序列化到 result.engine_warnings."""
    from app.pipeline import real_pipeline_v2 as mod
    from app.schemas import AnalyzeRequest, AnalyzeResult

    monkeypatch.setattr(
        mod, "_ffprobe_extended", lambda _: _probe(codec="hevc", has_audio=True)
    )

    async def _fake_v1(req, *, diagnose_fn=None, enrichment_fn=None):
        return AnalyzeResult(
            analysis_id=req.analysis_id,
            status="completed",
            overall_score=70,
            engine_warnings=[],
        )

    import app.pipeline.real_pipeline as v1_mod

    monkeypatch.setattr(v1_mod, "run_real_analysis", _fake_v1)

    req = AnalyzeRequest(
        analysis_id="t1",
        video_url="https://example.com/v.mov",
        club_type="iron_7",
        camera_angle="face_on",
    )

    import asyncio

    result = asyncio.run(mod.run_real_analysis_v2(req))
    codes = {w["code"] for w in result.engine_warnings}
    assert "decoded_hevc" in codes
    assert "audio_kept" in codes
    assert "fallback_to_v1" not in codes  # 资源正常加载，无 fallback


# ---------- P2-W9+ review fix（P1-2）：probe metrics 可观测性 ----------


def test_probe_metrics_increment_count_and_errors(monkeypatch):
    """probe 调用应 incr v2_probe_count；失败时 incr v2_probe_errors."""
    from app import metrics

    metrics.reset()

    # case 1: 成功 probe → count+1, errors+0
    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", lambda _: _probe(codec="h264"))
    _probe_video_warnings("https://example.com/v.mp4")
    snap = metrics.snapshot()
    assert snap["v2_probe_count"] == 1
    assert snap["v2_probe_errors"] == 0
    assert snap["v2_probe_error_rate"] == 0.0

    # case 2: 失败 probe → count+1, errors+1
    def _raise(_):
        raise RuntimeError("ffprobe boom")

    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", _raise)
    _probe_video_warnings("https://example.com/v2.mp4")
    snap2 = metrics.snapshot()
    assert snap2["v2_probe_count"] == 2
    assert snap2["v2_probe_errors"] == 1
    assert snap2["v2_probe_error_rate"] == 0.5  # 1/2


def test_probe_metrics_skip_count_on_empty_url():
    """空 URL 提前 return，不消耗 probe_count 计数（避免 ratio 被假信号污染）."""
    from app import metrics

    metrics.reset()
    _probe_video_warnings("")
    snap = metrics.snapshot()
    assert snap["v2_probe_count"] == 0
    assert snap["v2_probe_errors"] == 0


def test_run_real_analysis_v2_appends_fallback_when_v2_resources_missing(
    monkeypatch,
):
    """V2 资源加载失败 → probe + fallback 两类 warning 合并；
    并且 ``_enrich_v2_fallback`` 会让 ``analysis_confidence`` 反映真 mean_visibility
    （不再 schema 默认 1.0 谎报高可信——P2-W9+ review P1-1）."""
    from app.pipeline import real_pipeline_v2 as mod
    from app.schemas import AnalyzeRequest, AnalyzeResult

    monkeypatch.setattr(
        mod, "_ffprobe_extended", lambda _: _probe(codec="h264", has_audio=False)
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("v2 yaml corrupted")

    monkeypatch.setattr(mod, "_get_rules", _raise)

    # _fake_v1 模拟「V1 跑出来 result」，并真调 enrichment_fn=_enrich_v2_fallback 让
    # analysis_confidence 反映 mean_vis（base=0.5、qw=1.0、feat_avg=1.0 → 0.5）
    import numpy as np

    from app.pipeline.phases import PhaseInfo, PhaseSegmentResult
    from app.pipeline.pose import (
        LANDMARK_LEFT_SHOULDER,
        LANDMARK_LEFT_WRIST,
        PoseResult,
    )
    from app.pipeline.real_pipeline import PipelineCtx

    async def _fake_v1(req, *, diagnose_fn=None, enrichment_fn=None):
        result = AnalyzeResult(
            analysis_id=req.analysis_id,
            status="completed",
            overall_score=70,
        )
        if enrichment_fn is not None:
            pose = PoseResult(
                keypoints=np.zeros((30, 33, 3), dtype=np.float32),
                visibility=np.full((30, 33), 0.5, dtype=np.float32),
                valid_mask=np.ones(30, dtype=bool),
                num_frames=30,
                fps=30.0,
            )
            phases = PhaseSegmentResult(
                phases={
                    "setup": PhaseInfo(0, 4, 2),
                    "backswing": PhaseInfo(5, 14, 10),
                    "top": PhaseInfo(15, 15, 15),
                    "downswing": PhaseInfo(16, 19, 18),
                    "impact": PhaseInfo(20, 20, 20),
                    "follow_through": PhaseInfo(21, 29, 25),
                },
                top_frame=15, impact_frame=20,
                swing_start=5, swing_end=20,
                handedness="right",
                lead_wrist_idx=LANDMARK_LEFT_WRIST,
                lead_shoulder_idx=LANDMARK_LEFT_SHOULDER,
                fps=30.0,
            )
            ctx = PipelineCtx(
                pose_result=pose,
                phases=phases,
                features={},
                quality_warnings=[],
                fps=30.0,
            )
            enrichment_fn(result, ctx)
        return result

    import app.pipeline.real_pipeline as v1_mod

    monkeypatch.setattr(v1_mod, "run_real_analysis", _fake_v1)

    req = AnalyzeRequest(
        analysis_id="t2",
        video_url="https://example.com/v.mp4",
        club_type="iron_7",
        camera_angle="face_on",
    )

    import asyncio

    result = asyncio.run(mod.run_real_analysis_v2(req))
    codes = {w["code"] for w in result.engine_warnings}
    assert "decoded_h264" in codes
    assert "audio_dropped" in codes
    assert "fallback_to_v1" in codes
    # P1-1 fix：analysis_confidence 不应再是 schema 默认 1.0
    assert result.analysis_confidence < 1.0
    assert result.analysis_confidence == pytest.approx(0.5, abs=1e-3)


# ============================================================
# P2-W12-3 · MinIO ffprobe 5XX 治理（retry + 错误分类 + URL 脱敏）
# ============================================================


def test_classify_probe_error_buckets():
    """W12-3 · `_classify_probe_error` 把 ffprobe 失败粗分桶进窄集合."""
    import subprocess as sp

    from app.pipeline.real_pipeline_v2 import _classify_probe_error

    # 5xx 关键字
    assert (
        _classify_probe_error(
            RuntimeError("Server returned 503 Service Unavailable for ...")
        )
        == "5xx"
    )
    # 4xx 关键字
    assert (
        _classify_probe_error(RuntimeError("URL expired: signature mismatch"))
        == "4xx"
    )
    assert (
        _classify_probe_error(RuntimeError("Server returned 404 Not Found"))
        == "4xx"
    )
    # subprocess.TimeoutExpired 实例
    assert (
        _classify_probe_error(sp.TimeoutExpired(cmd=["ffprobe"], timeout=15))
        == "timeout"
    )
    # 二进制缺失
    assert (
        _classify_probe_error(
            RuntimeError("FileNotFoundError: ffprobe not found in PATH")
        )
        == "binary_missing"
    )
    # 兜底
    assert _classify_probe_error(RuntimeError("something weird")) == "unknown"


def test_sanitize_probe_url_strips_query_string():
    """W12-3 · MinIO 预签名 URL query 含 X-Amz-Signature，必须脱敏避免泄漏."""
    from app.pipeline.real_pipeline_v2 import _sanitize_probe_url

    raw = "https://minio.example.com/birdie/swing/abc.mp4?X-Amz-Signature=DEADBEEF&X-Amz-Expires=300"
    assert _sanitize_probe_url(raw) == "https://minio.example.com/birdie/swing/abc.mp4"
    assert _sanitize_probe_url("") == ""
    assert _sanitize_probe_url("https://x/y.mp4") == "https://x/y.mp4"


def test_probe_retries_5xx_then_succeeds(monkeypatch):
    """W12-3 · 5xx 触发 retry；第 2 次成功 → 不产 probe_failed warning + 仍出 codec warnings."""
    from app import metrics

    metrics.reset()
    calls = {"n": 0}

    def _flaky(_):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Server returned 503 Service Unavailable")
        return _probe(codec="h264")

    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", _flaky)
    # 避免真睡 0.5s
    monkeypatch.setattr(rp2_mod.time, "sleep", lambda *_: None)

    warnings = _probe_video_warnings("https://x/v.mp4?sig=xx")
    codes = {w.code for w in warnings}
    assert "decoded_h264" in codes
    assert "probe_failed" not in codes
    # 一次 retry → v2_probe_retries 计数 1
    snap = metrics.snapshot()
    assert snap["v2_probe_retries"] == 1
    assert calls["n"] == 2


def test_probe_5xx_all_attempts_fail_emits_probe_failed_warning(monkeypatch):
    """W12-3 · 5xx 全部 3 次都失败 → probe_failed warning reason=5xx + metrics 分桶."""
    from app import metrics

    metrics.reset()

    def _raise_5xx(_):
        raise RuntimeError("Server returned 502 Bad Gateway")

    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", _raise_5xx)
    monkeypatch.setattr(rp2_mod.time, "sleep", lambda *_: None)

    warnings = _probe_video_warnings("https://x/v.mp4?sig=yy")
    assert len(warnings) == 1
    assert warnings[0].code == "probe_failed"
    assert "reason=5xx" in warnings[0].detail
    assert "attempts=3" in warnings[0].detail
    snap = metrics.snapshot()
    assert snap["v2_probe_errors"] == 1
    assert snap["v2_probe_retries"] == 2  # 第 1 / 第 2 次失败各 1 次 retry
    assert snap["v2_probe_errors_5xx_after_retries"] == 1


def test_probe_4xx_does_not_retry(monkeypatch):
    """W12-3 · 4xx (URL 过期) retry 没用，应**立即放弃**避免拖慢 pipeline."""
    from app import metrics

    metrics.reset()
    calls = {"n": 0}

    def _raise_4xx(_):
        calls["n"] += 1
        raise RuntimeError("URL expired: X-Amz signature invalid")

    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", _raise_4xx)
    monkeypatch.setattr(rp2_mod.time, "sleep", lambda *_: None)

    warnings = _probe_video_warnings("https://x/v.mp4?sig=zz")
    assert len(warnings) == 1
    assert warnings[0].code == "probe_failed"
    assert "reason=4xx" in warnings[0].detail
    # 4xx 不 retry，只调一次 ffprobe
    assert calls["n"] == 1
    snap = metrics.snapshot()
    assert snap["v2_probe_retries"] == 0
    assert snap["v2_probe_errors_4xx"] == 1


def test_probe_timeout_retries_like_5xx(monkeypatch):
    """W12-3 · subprocess.TimeoutExpired 同样触发 retry（短暂超时也属临时性故障）."""
    import subprocess as sp

    from app import metrics

    metrics.reset()
    calls = {"n": 0}

    def _flaky_timeout(_):
        calls["n"] += 1
        if calls["n"] < 3:
            raise sp.TimeoutExpired(cmd=["ffprobe"], timeout=15)
        return _probe(codec="h264")

    monkeypatch.setattr(rp2_mod, "_ffprobe_extended", _flaky_timeout)
    monkeypatch.setattr(rp2_mod.time, "sleep", lambda *_: None)

    warnings = _probe_video_warnings("https://x/v.mp4")
    codes = {w.code for w in warnings}
    assert "decoded_h264" in codes  # 第 3 次成功
    assert "probe_failed" not in codes
    snap = metrics.snapshot()
    assert snap["v2_probe_retries"] == 2  # 第 1 / 第 2 次 timeout 各 1 次 retry
    assert calls["n"] == 3


def test_probe_failed_in_KNOWN_CODES():
    """W12-3 · ``probe_failed`` 必须注册到 engine_warnings.KNOWN_CODES 白名单."""
    from app.pipeline.engine_warnings import KNOWN_CODES

    assert "probe_failed" in KNOWN_CODES
