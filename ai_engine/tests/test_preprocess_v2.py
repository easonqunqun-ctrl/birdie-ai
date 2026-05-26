"""P2-M7-02 · 视频读取增强 V2 单元测试。

测试覆盖：
1. `DecodeError(50120)` 错误类（kickoff §3.1）
2. `EngineWarning` 数据结构 + truncate（kickoff §4.2）
3. `_parse_ffprobe_json` 各类样本（HEVC / HDR / VP9 / 慢动作 / 老 H264）
4. `_validate_codec` 白名单
5. V1 行为冻结（preprocess.py 模块顶层常量未被 V2 修改）

设计原则：不依赖真实视频文件；ffprobe JSON 用 fixture 字典构造，subprocess 不会被调起。
"""

from __future__ import annotations

import pytest

from app.errors import DecodeError, PreprocessError
from app.pipeline.engine_warnings import (
    MAX_DETAIL_LEN,
    MAX_ENGINE_WARNINGS,
    EngineWarning,
    serialize_engine_warnings,
    truncate_engine_warnings,
)
from app.pipeline.preprocess_v2 import (
    SUPPORTED_CODECS,
    _parse_ffprobe_json,
    _validate_codec,
)
import json


# ============================================================
# 1. DecodeError 错误类
# ============================================================


def test_decode_error_code_50120():
    err = DecodeError("hevc decoder not found")
    assert err.code == 50120
    assert "格式" in err.user_message
    d = err.to_dict()
    assert d["code"] == 50120
    assert d["detail"] == "hevc decoder not found"


def test_decode_error_custom_user_message():
    err = DecodeError("vp9 fail", user_message="自定义文案")
    assert err.user_message == "自定义文案"
    assert err.code == 50120


def test_decode_error_distinct_from_preprocess_error():
    assert DecodeError("").code != PreprocessError("").code
    assert DecodeError("").code == 50120
    assert PreprocessError("").code == 50101


# ============================================================
# 2. EngineWarning 数据结构
# ============================================================


def test_engine_warning_default_level_info():
    w = EngineWarning(code="decoded_hevc", detail="codec=hevc")
    assert w.level == "info"
    assert w.code == "decoded_hevc"
    assert w.ts  # ISO timestamp filled
    assert "T" in w.ts


def test_engine_warning_invalid_level_coerced_to_info():
    w = EngineWarning(code="x", level="critical")  # type: ignore[arg-type]
    assert w.level == "info"


def test_engine_warning_detail_truncated_to_max_len():
    long_detail = "x" * (MAX_DETAIL_LEN + 50)
    w = EngineWarning(code="x", detail=long_detail)
    assert len(w.detail) == MAX_DETAIL_LEN


def test_truncate_engine_warnings_below_max_returns_as_is():
    warnings = [EngineWarning(code=f"c{i}") for i in range(10)]
    out = truncate_engine_warnings(warnings)
    assert out == warnings
    assert len(out) == 10


def test_truncate_engine_warnings_above_max_truncates_with_marker():
    warnings = [EngineWarning(code=f"c{i}") for i in range(MAX_ENGINE_WARNINGS + 5)]
    out = truncate_engine_warnings(warnings)
    assert len(out) == MAX_ENGINE_WARNINGS
    assert out[-1].code == "engine_warnings_truncated"
    assert out[-1].level == "warn"


def test_serialize_engine_warnings_is_list_of_dicts():
    warnings = [EngineWarning(code="decoded_hevc"), EngineWarning(code="audio_kept")]
    out = serialize_engine_warnings(warnings)
    assert isinstance(out, list)
    assert all(isinstance(d, dict) for d in out)
    assert {d["code"] for d in out} == {"decoded_hevc", "audio_kept"}
    assert all({"code", "level", "detail", "ts"} <= set(d.keys()) for d in out)


# ============================================================
# 3. _parse_ffprobe_json fixtures
# ============================================================


def _ffprobe_json(
    *,
    codec: str = "h264",
    pix_fmt: str = "yuv420p",
    width: int = 1080,
    height: int = 1920,
    fps: str = "30/1",
    duration: float = 5.0,
    container: str = "mov,mp4,m4a,3gp,3g2,mj2",
    color_space: str = "bt709",
    color_transfer: str = "bt709",
    color_primaries: str = "bt709",
    has_audio: bool = True,
    nominal_fps: float | None = None,
) -> str:
    """生成模拟 ffprobe JSON 输出。"""
    v_stream = {
        "codec_type": "video",
        "codec_name": codec,
        "pix_fmt": pix_fmt,
        "width": width,
        "height": height,
        "r_frame_rate": fps,
        "color_space": color_space,
        "color_transfer": color_transfer,
        "color_primaries": color_primaries,
    }
    if nominal_fps is not None:
        v_stream["tags"] = {"nominal_frame_rate": str(nominal_fps)}

    streams = [v_stream]
    if has_audio:
        streams.append({"codec_type": "audio", "codec_name": "aac"})

    return json.dumps(
        {
            "streams": streams,
            "format": {
                "format_name": container,
                "duration": str(duration),
            },
        }
    )


def test_parse_ffprobe_basic_h264():
    out = _parse_ffprobe_json(_ffprobe_json())
    assert out.codec_name == "h264"
    assert out.width == 1080
    assert out.height == 1920
    assert abs(out.fps_raw - 30.0) < 0.01
    assert out.has_audio is True
    assert out.is_hdr is False
    assert out.is_10bit is False
    assert out.is_slowmo is False


def test_parse_ffprobe_hevc_10bit_hdr():
    out = _parse_ffprobe_json(
        _ffprobe_json(
            codec="hevc",
            pix_fmt="yuv420p10le",
            color_space="bt2020nc",
            color_transfer="smpte2084",
            color_primaries="bt2020",
        )
    )
    assert out.codec_name == "hevc"
    assert out.is_10bit is True
    assert out.is_hdr is True
    assert out.color_transfer == "smpte2084"


def test_parse_ffprobe_vp9_webm():
    out = _parse_ffprobe_json(
        _ffprobe_json(
            codec="vp9",
            container="matroska,webm",
            fps="60/1",
        )
    )
    assert out.codec_name == "vp9"
    assert "webm" in out.container_format_name
    assert abs(out.fps_raw - 60.0) < 0.01


def test_parse_ffprobe_slowmo_240fps_with_nominal_30():
    out = _parse_ffprobe_json(
        _ffprobe_json(
            fps="240/1",
            nominal_fps=30.0,
        )
    )
    assert abs(out.fps_raw - 240.0) < 0.01
    assert out.nominal_fps == 30.0
    assert out.is_slowmo is True


def test_parse_ffprobe_120fps_not_slowmo_if_no_nominal():
    out = _parse_ffprobe_json(_ffprobe_json(fps="120/1", nominal_fps=None))
    assert abs(out.fps_raw - 120.0) < 0.01
    assert out.nominal_fps == 0.0
    assert out.is_slowmo is False


def test_parse_ffprobe_no_audio_stream():
    out = _parse_ffprobe_json(_ffprobe_json(has_audio=False))
    assert out.has_audio is False


def test_parse_ffprobe_raises_on_no_video_stream():
    j = json.dumps({"streams": [{"codec_type": "audio"}], "format": {}})
    with pytest.raises(PreprocessError):
        _parse_ffprobe_json(j)


def test_parse_ffprobe_raises_on_invalid_json():
    with pytest.raises(PreprocessError):
        _parse_ffprobe_json("not json{")


# ============================================================
# 4. _validate_codec 白名单
# ============================================================


def test_validate_codec_h264_passes():
    out = _parse_ffprobe_json(_ffprobe_json(codec="h264"))
    _validate_codec(out, [])  # no raise


def test_validate_codec_hevc_passes():
    out = _parse_ffprobe_json(_ffprobe_json(codec="hevc"))
    _validate_codec(out, [])


def test_validate_codec_rejects_unknown_codec_with_50120():
    out = _parse_ffprobe_json(_ffprobe_json(codec="prores"))
    with pytest.raises(DecodeError) as excinfo:
        _validate_codec(out, [])
    assert excinfo.value.code == 50120


def test_validate_codec_rejects_empty_codec():
    out = _parse_ffprobe_json(_ffprobe_json())
    out.codec_name = ""
    with pytest.raises(DecodeError):
        _validate_codec(out, [])


def test_supported_codecs_whitelist_immutable():
    assert "h264" in SUPPORTED_CODECS
    assert "hevc" in SUPPORTED_CODECS
    assert "vp9" in SUPPORTED_CODECS
    assert "prores" not in SUPPORTED_CODECS
    with pytest.raises(AttributeError):
        SUPPORTED_CODECS.add("prores")  # type: ignore[attr-defined]


# ============================================================
# 5. V1 行为冻结（确认 V2 没意外篡改 V1 常量）
# ============================================================


def test_v1_constants_frozen():
    """kickoff §10.3 V1 行为不可改。"""
    from app.pipeline import preprocess as v1

    assert v1.TARGET_FPS == 30
    assert v1.TARGET_SHORT_SIDE == 720
    assert v1.TARGET_VCODEC == "libx264"
    assert v1.TARGET_PIX_FMT == "yuv420p"


def test_v2_constants_differ_from_v1():
    """V2 引入的关键变更必须与 V1 区分。"""
    from app.pipeline import preprocess as v1
    from app.pipeline import preprocess_v2 as v2

    assert v2.TARGET_FPS_V2 == 60
    assert v2.TARGET_FPS_V2 != v1.TARGET_FPS
    assert v2.TARGET_ACODEC_V2 == "aac"  # FR-6


def test_engine_warning_known_codes_cover_kickoff_examples():
    """kickoff §4.2 列举的 code 必须在 KNOWN_CODES 里。"""
    from app.pipeline.engine_warnings import KNOWN_CODES

    for code in ("decoded_hevc", "hdr_tonemapped", "fps_upsampled", "audio_kept"):
        assert code in KNOWN_CODES
