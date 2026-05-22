"""assets 同源代理：samples/ 前缀允许列表（练习示范、示例报告素材）。"""

from app.api.v1 import assets as assets_module


def test_samples_prefix_allowed_for_video_and_image() -> None:
    assert "samples/" in assets_module.ALLOWED_VIDEO_PREFIXES
    assert "samples/" in assets_module.ALLOWED_IMAGE_PREFIXES
    assert any("samples/swing_demo.mp4".startswith(p) for p in assets_module.ALLOWED_VIDEO_PREFIXES)
    assert any(
        "samples/swing_demo_thumb.jpg".startswith(p)
        for p in assets_module.ALLOWED_IMAGE_PREFIXES
    )
