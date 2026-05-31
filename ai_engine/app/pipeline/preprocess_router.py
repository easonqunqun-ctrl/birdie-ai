"""P2-M7-R1-B7 / P2-M7-02 · preprocess V1/V2 路由（opt-in 灰度）。

契约：仅 ``engine_version == "v2"`` 且 ``M7_VIDEO_READER_V2_ENABLED=true`` 时走 V2；
V1 主链与 detect-swings 默认仍用 ``preprocess_video``（30fps）。
"""

from __future__ import annotations

from app.config import settings
from app.pipeline.engine_warnings import serialize_engine_warnings
from app.pipeline.preprocess import PreprocessResult, preprocess_video
from app.pipeline.preprocess_v2 import preprocess_video_v2

ENGINE_V2 = "v2"


def should_use_preprocess_v2(*, engine_version: str | None = None) -> bool:
    """是否在本请求使用 ``preprocess_video_v2``（60fps / HEVC 等）。"""
    if not settings.M7_VIDEO_READER_V2_ENABLED:
        return False
    if engine_version is not None and engine_version != ENGINE_V2:
        return False
    return True


def preprocess_for_pipeline(
    video_url: str,
    *,
    use_v2: bool,
) -> tuple[PreprocessResult, list[dict], str]:
    """返回 (预处理结果, engine_warnings 序列化, reader_version 标签)。"""
    if use_v2:
        pre = preprocess_video_v2(video_url)
        return pre, serialize_engine_warnings(pre.engine_warnings), "v2"
    pre = preprocess_video(video_url)
    return pre, [], "v1"
