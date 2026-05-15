"""生产门禁 audit_production_config / startup_production_guards."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.core.production_guard import audit_production_config, startup_production_guards


def _prod_aligned_minio_kw() -> dict:
    """与 effective_minio 回落 + https API 组合的合法最小集。"""
    return {
        "APP_ENV": "prod",
        "WECHAT_MOCK_LOGIN": False,
        "WECHAT_MINIPROGRAM_APPID": "wxdeadbeef00000000",
        "WECHAT_MINIPROGRAM_SECRET": "real_wx_secret_value_not_placeholder",
        "APP_SECRET_KEY": "app_secret_forty_characters_minimum_len_x",
        "JWT_SECRET_KEY": "jwt_secret_must_be_long_enough_value_ok",
        "API_PUBLIC_BASE_URL": "https://api.example.com",
        "STORAGE_PROVIDER": "minio",
        "MINIO_PUBLIC_ENDPOINT": "http://localhost:9000",
        # 非占位，避免所有「门禁通过」用例都带上 FakeLLM 告警噪声
        "LLM_API_KEY": "deepseek-integration-key-not-placeholder-abcdef",
    }


class _SilentLogger:
    def warning(self, *a: object, **k: object) -> None:
        pass

    def error(self, *a: object, **k: object) -> None:
        pass


def test_audit_passes_aligned_minio_and_https_api() -> None:
    errs, warns = audit_production_config(Settings(**_prod_aligned_minio_kw()))
    assert errs == []
    assert not any("FakeLLM" in w for w in warns)


def test_audit_warns_placeholder_llm_api_key_in_prod() -> None:
    kw = _prod_aligned_minio_kw()
    kw["LLM_API_KEY"] = ""
    errs, warns = audit_production_config(Settings(**kw))
    assert errs == []
    assert any("FakeLLM" in w for w in warns)


def test_audit_warns_explicit_llm_mock() -> None:
    kw = _prod_aligned_minio_kw()
    kw["LLM_MOCK_MODE"] = True
    errs, warns = audit_production_config(Settings(**kw))
    assert errs == []
    assert any("FakeLLM" in w for w in warns)


def test_audit_rejects_mock_login() -> None:
    kw = _prod_aligned_minio_kw()
    kw["WECHAT_MOCK_LOGIN"] = True
    errs, _ = audit_production_config(Settings(**kw))
    assert any("WECHAT_MOCK_LOGIN" in e for e in errs)


def test_audit_rejects_quota_unlimited_in_prod() -> None:
    kw = _prod_aligned_minio_kw()
    kw["QUOTA_MODE"] = "unlimited"
    errs, _ = audit_production_config(Settings(**kw))
    assert any("QUOTA_MODE" in e for e in errs)


def test_audit_rejects_angle_bracket_template_in_database_url() -> None:
    kw = _prod_aligned_minio_kw()
    kw["DATABASE_URL"] = (
        "postgresql+asyncpg://xiaoniao:<change-me-strong-password>@postgres:5432/xiaoniao"
    )
    errs, _ = audit_production_config(Settings(**kw))
    assert any("尖括号" in e for e in errs)


def test_audit_rejects_trycloudflare_minio_public() -> None:
    kw = _prod_aligned_minio_kw()
    kw["MINIO_PUBLIC_ENDPOINT"] = "https://rugs-tar-wishlist-accountability.trycloudflare.com"
    errs, _ = audit_production_config(Settings(**kw))
    assert any("穿透" in e for e in errs)


def test_audit_rejects_http_api_public() -> None:
    kw = _prod_aligned_minio_kw()
    kw["API_PUBLIC_BASE_URL"] = "http://api.example.com"
    errs, _ = audit_production_config(Settings(**kw))
    assert any("https" in e.lower() for e in errs)


def test_audit_cos_requires_bucket_and_keys() -> None:
    kw = _prod_aligned_minio_kw()
    kw.update({
        "STORAGE_PROVIDER": "cos",
        "COS_BUCKET": "",
        "COS_SECRET_ID": "",
        "COS_SECRET_KEY": "",
    })
    errs, _ = audit_production_config(Settings(**kw))
    assert len(errs) >= 2


def test_startup_prod_raises_when_errors() -> None:
    kw = _prod_aligned_minio_kw()
    kw["WECHAT_MOCK_LOGIN"] = True
    with pytest.raises(RuntimeError, match="生产门禁"):
        startup_production_guards(_SilentLogger(), Settings(**kw))


def test_startup_staging_never_raises_from_guard() -> None:
    kw = _prod_aligned_minio_kw()
    kw["APP_ENV"] = "staging"
    kw["WECHAT_MOCK_LOGIN"] = True
    startup_production_guards(_SilentLogger(), Settings(**kw))
