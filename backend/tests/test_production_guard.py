"""生产门禁 audit_production_config / startup_production_guards."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.core.production_guard import (
    audit_production_config,
    audit_wechat_pay_real_mode,
    audit_wechat_xpay_enabled,
    startup_production_guards,
)


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


def test_audit_wechat_pay_real_mode_empty_when_mock() -> None:
    s = Settings(WECHAT_PAY_MOCK_MODE=True, WECHAT_PAY_MCH_ID="")
    assert audit_wechat_pay_real_mode(s) == []


def test_audit_pay_cert_file_must_exist_when_using_cert_path() -> None:
    kw = _prod_aligned_minio_kw()
    kw["WECHAT_PAY_MOCK_MODE"] = False
    kw["WECHAT_PAY_MCH_ID"] = "1900000109"
    kw["WECHAT_PAY_MCH_SERIAL"] = "SERIALOK01"
    kw["WECHAT_PAY_API_V3_KEY"] = "a" * 32
    kw["WECHAT_PAY_NOTIFY_URL"] = "https://api.example.com/v1/payments/wechat/notify"
    kw["WECHAT_PAY_PRIVATE_KEY_PEM"] = ""
    kw["WECHAT_PAY_CERT_PATH"] = "/tmp/__nonexistent_apiclient_for_audit_test__.pem"
    errs = audit_wechat_pay_real_mode(Settings(**kw))
    assert any("进程内不存在" in e or "不可读" in e for e in errs)


def test_audit_wechat_pay_real_mode_requires_apiv3_length() -> None:
    kw = _prod_aligned_minio_kw()
    kw["WECHAT_PAY_MOCK_MODE"] = False
    kw["WECHAT_PAY_MCH_ID"] = "1900000109"
    kw["WECHAT_PAY_MCH_SERIAL"] = "7F42F1C123ABCD"
    kw["WECHAT_PAY_API_V3_KEY"] = "tooshort"
    kw["WECHAT_PAY_NOTIFY_URL"] = "https://api.example.com/v1/payments/wechat/notify"
    kw["WECHAT_PAY_PRIVATE_KEY_PEM"] = (
        "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQ\n-----END PRIVATE KEY-----\n"
    )
    errs = audit_wechat_pay_real_mode(Settings(**kw))
    assert any("32" in e for e in errs)


def test_startup_staging_raises_when_real_pay_incomplete() -> None:
    kw = _prod_aligned_minio_kw()
    kw["APP_ENV"] = "staging"
    kw["WECHAT_PAY_MOCK_MODE"] = False
    kw["WECHAT_PAY_MCH_ID"] = "1900000109"
    kw["WECHAT_PAY_API_V3_KEY"] = "a" * 32
    kw["WECHAT_PAY_NOTIFY_URL"] = "https://api.example.com/v1/payments/wechat/notify"
    kw["WECHAT_PAY_PRIVATE_KEY_PEM"] = (
        "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQ\n-----END PRIVATE KEY-----\n"
    )
    # 缺证书序列号 → 启动门禁应直接失败（与线上下单 502 同源问题）
    kw["WECHAT_PAY_MCH_SERIAL"] = ""
    with pytest.raises(RuntimeError, match="微信支付"):
        startup_production_guards(_SilentLogger(), Settings(**kw))


def test_startup_prod_combines_general_and_pay_errors() -> None:
    kw = _prod_aligned_minio_kw()
    kw["WECHAT_MOCK_LOGIN"] = True  # prod 常规门禁已不通过
    kw["WECHAT_PAY_MOCK_MODE"] = False
    kw["WECHAT_PAY_MCH_ID"] = "1900000109"
    kw["WECHAT_PAY_API_V3_KEY"] = "a" * 32
    kw["WECHAT_PAY_NOTIFY_URL"] = "https://api.example.com/v1/payments/wechat/notify"
    kw["WECHAT_PAY_PRIVATE_KEY_PEM"] = (
        "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQ\n-----END PRIVATE KEY-----\n"
    )
    kw["WECHAT_PAY_MCH_SERIAL"] = "SERIAL1"
    with pytest.raises(RuntimeError, match="生产门禁"):
        startup_production_guards(_SilentLogger(), Settings(**kw))


def _xpay_aligned_kw() -> dict:
    kw = _prod_aligned_minio_kw()
    kw.update({
        "WECHAT_PAY_MOCK_MODE": False,
        "WECHAT_XPAY_ENABLED": True,
        "WECHAT_XPAY_OFFER_ID": "offer123",
        "WECHAT_XPAY_APP_KEY": "app_key_prod",
        "WECHAT_XPAY_SANDBOX_APP_KEY": "app_key_sandbox",
        "WECHAT_XPAY_ENV": 0,
        "WECHAT_XPAY_PRODUCT_MONTHLY": "prod_monthly",
        "WECHAT_XPAY_PRODUCT_YEARLY": "prod_yearly",
        "WECHAT_MP_PUSH_TOKEN": "mp_push_token",
        "WECHAT_PAY_MCH_ID": "1900000109",
        "WECHAT_PAY_MCH_SERIAL": "SERIALOK01",
        "WECHAT_PAY_API_V3_KEY": "a" * 32,
        "WECHAT_PAY_NOTIFY_URL": "https://api.example.com/v1/payments/wechat/notify",
        "WECHAT_PAY_PRIVATE_KEY_PEM": (
            "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQ\n-----END PRIVATE KEY-----\n"
        ),
    })
    return kw


def test_audit_wechat_xpay_disabled_returns_empty() -> None:
    s = Settings(**_prod_aligned_minio_kw())
    assert audit_wechat_xpay_enabled(s) == []


def test_audit_wechat_xpay_enabled_requires_offer_and_products() -> None:
    kw = _xpay_aligned_kw()
    kw["WECHAT_XPAY_OFFER_ID"] = ""
    kw["WECHAT_XPAY_PRODUCT_YEARLY"] = ""
    errs = audit_wechat_xpay_enabled(Settings(**kw))
    assert any("WECHAT_XPAY_OFFER_ID" in e for e in errs)
    assert any("WECHAT_XPAY_PRODUCT_YEARLY" in e for e in errs)


def test_audit_wechat_xpay_sandbox_requires_sandbox_app_key() -> None:
    kw = _xpay_aligned_kw()
    kw["WECHAT_XPAY_ENV"] = 1
    kw["WECHAT_XPAY_SANDBOX_APP_KEY"] = ""
    errs = audit_wechat_xpay_enabled(Settings(**kw))
    assert any("SANDBOX" in e for e in errs)


def test_startup_staging_raises_when_xpay_enabled_incomplete() -> None:
    kw = _xpay_aligned_kw()
    kw["APP_ENV"] = "staging"
    kw["WECHAT_MP_PUSH_TOKEN"] = ""
    with pytest.raises(RuntimeError, match="WECHAT_MP_PUSH_TOKEN"):
        startup_production_guards(_SilentLogger(), Settings(**kw))
