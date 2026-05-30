"""assets 同源代理：samples/ 前缀允许列表（练习示范、示例报告素材）。"""

from app.api.v1 import assets as assets_module


def test_samples_prefix_allowed_for_video_and_image() -> None:
    assert "samples/" in assets_module.ALLOWED_VIDEO_PREFIXES
    assert "samples/" in assets_module.ALLOWED_IMAGE_PREFIXES
    assert any("samples/swing_demo.mp4".startswith(p) for p in assets_module.ALLOWED_VIDEO_PREFIXES)
    assert any("pro-clips/kanagawa.webm".startswith(p) for p in assets_module.ALLOWED_VIDEO_PREFIXES)


def test_to_proxy_video_url_rewrites_pro_clips(monkeypatch) -> None:
    import app.services.analysis_service as svc
    from app.config import Settings

    s = Settings(
        APP_ENV="prod",
        STORAGE_PROVIDER="minio",
        MINIO_PUBLIC_ENDPOINT="https://api.example.com/minio",
        API_PUBLIC_BASE_URL="https://api.example.com",
        MINIO_BUCKET="bkt",
    )
    monkeypatch.setattr(svc, "settings", s)
    raw = "https://api.example.com/minio/bkt/pro-clips/kanagawa.webm"
    assert svc.to_proxy_video_url(raw) == (
        "https://api.example.com/v1/assets/video/pro-clips/kanagawa.webm"
    )


def test_to_proxy_video_url_rewrites_samples(monkeypatch) -> None:
    import app.services.analysis_service as svc
    from app.config import Settings

    s = Settings(
        APP_ENV="prod",
        STORAGE_PROVIDER="minio",
        MINIO_PUBLIC_ENDPOINT="https://api.example.com/minio",
        API_PUBLIC_BASE_URL="https://api.example.com",
        MINIO_BUCKET="bkt",
    )
    monkeypatch.setattr(svc, "settings", s)
    raw = "https://api.example.com/minio/bkt/samples/swing_demo.mp4"
    assert svc.to_proxy_video_url(raw) == (
        "https://api.example.com/v1/assets/video/samples/swing_demo.mp4"
    )
