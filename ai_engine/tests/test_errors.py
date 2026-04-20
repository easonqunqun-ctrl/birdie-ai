"""错误类单元测试（不依赖视频/MediaPipe/ffmpeg，任何环境都能跑）。"""

from __future__ import annotations

from app.errors import (
    NoPersonError,
    NoSwingError,
    PipelineError,
    PoorQualityError,
    PoseModelError,
    PreprocessError,
)


def test_error_code_mapping() -> None:
    """确保 50101-50105 段错误码与类一一对应（docs/02 §1.4 约定）。"""
    assert PreprocessError.code == 50101
    assert PoorQualityError.code == 50102
    assert NoPersonError.code == 50103
    assert NoSwingError.code == 50104
    assert PoseModelError.code == 50105


def test_all_subclass_of_pipeline_error() -> None:
    """main.py::analyze 的 try/except 只 catch PipelineError 基类，
    所以新加的错误类必须继承基类。"""
    for cls in (PreprocessError, PoorQualityError, NoPersonError, NoSwingError, PoseModelError):
        assert issubclass(cls, PipelineError)


def test_error_has_user_message() -> None:
    """每个错误都要有面向用户的中文 user_message，避免把 Python traceback 直接返给前端。"""
    for cls in (PreprocessError, PoorQualityError, NoPersonError, NoSwingError, PoseModelError):
        instance = cls("internal detail")
        assert instance.user_message
        assert len(instance.user_message) > 0


def test_error_to_dict_shape() -> None:
    err = PoorQualityError("clarity=30 < 80", user_message="画质不足")
    payload = err.to_dict()
    assert payload["code"] == 50102
    assert payload["message"] == "画质不足"
    assert payload["detail"] == "clarity=30 < 80"


def test_error_user_message_override() -> None:
    """允许实例化时覆盖默认 user_message，用于根据具体场景细化文案。"""
    err = PreprocessError("ffmpeg timeout", user_message="视频太大，请压缩后重试")
    assert err.user_message == "视频太大，请压缩后重试"
    # 但 code 不变
    assert err.code == 50101
