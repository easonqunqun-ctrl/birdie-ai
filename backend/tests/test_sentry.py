"""Sentry 接入回归（PMF 监控告警基础设施）。

覆盖范围
--------
1. DSN 为空时 ``setup_sentry()`` no-op，不抛错、不调 ``sentry_sdk.init``。
2. DSN 非空时确实调 ``sentry_sdk.init``，并传入正确的 environment / release / sample rates。
3. 同进程重复调用幂等（fork worker / FastAPI + Celery 都调一次的常见场景）。
4. Settings 字段读取正确，默认值符合「PMF 期最低噪音」基线。

不做的事
--------
- 真发请求到 Sentry：CI 无网络出 sentry.io，测试只 mock ``sentry_sdk.init``。
- 测试 FastAPI / Celery integration 行为：那是 sentry-sdk 自己的单元测试范围，
  我们只断「我们传给它的参数对」+「该调的时候调了」。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.config import settings
from app.core import sentry as sentry_mod


@pytest.fixture(autouse=True)
def _reset_sentry_state() -> None:
    """每个用例前后都重置 ``_initialized`` 标志，避免相互污染。"""
    sentry_mod.reset_for_tests()
    yield
    sentry_mod.reset_for_tests()


def test_setup_sentry_noop_when_dsn_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """DSN 为空 → 返回 False，且 ``sentry_sdk.init`` 不应被调用。"""
    monkeypatch.setattr(settings, "SENTRY_DSN", "")

    with patch("app.core.sentry.sentry_sdk.init") as mocked_init:
        ok = sentry_mod.setup_sentry()

    assert ok is False
    assert mocked_init.call_count == 0


def test_setup_sentry_inits_when_dsn_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """DSN 非空 → 调用 ``sentry_sdk.init`` 一次，且传入的关键参数与 settings 对齐。"""
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://abc@example.ingest.sentry.io/1")
    monkeypatch.setattr(settings, "APP_ENV", "prod")
    monkeypatch.setattr(settings, "SENTRY_ENVIRONMENT", "")  # 走 fallback → APP_ENV
    monkeypatch.setattr(settings, "SENTRY_RELEASE", "")  # 走 fallback → __version__
    monkeypatch.setattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.1)
    monkeypatch.setattr(settings, "SENTRY_PROFILES_SAMPLE_RATE", 0.0)
    monkeypatch.setattr(settings, "SENTRY_SEND_DEFAULT_PII", False)

    with patch("app.core.sentry.sentry_sdk.init") as mocked_init:
        ok = sentry_mod.setup_sentry()

    assert ok is True
    assert mocked_init.call_count == 1
    kwargs = mocked_init.call_args.kwargs
    assert kwargs["dsn"] == "https://abc@example.ingest.sentry.io/1"
    assert kwargs["environment"] == "prod"
    assert kwargs["traces_sample_rate"] == 0.1
    assert kwargs["profiles_sample_rate"] == 0.0
    assert kwargs["send_default_pii"] is False
    # 三个 integration 都注册了
    integration_names = {type(i).__name__ for i in kwargs["integrations"]}
    assert integration_names == {
        "StarletteIntegration",
        "FastApiIntegration",
        "CeleryIntegration",
    }


def test_setup_sentry_respects_explicit_environment_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """显式 SENTRY_ENVIRONMENT / SENTRY_RELEASE 覆盖 fallback。"""
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://x@example.ingest.sentry.io/1")
    monkeypatch.setattr(settings, "APP_ENV", "staging")
    monkeypatch.setattr(settings, "SENTRY_ENVIRONMENT", "canary")
    monkeypatch.setattr(settings, "SENTRY_RELEASE", "abc1234")

    with patch("app.core.sentry.sentry_sdk.init") as mocked_init:
        sentry_mod.setup_sentry()

    kwargs = mocked_init.call_args.kwargs
    assert kwargs["environment"] == "canary"  # 覆盖了 APP_ENV
    assert kwargs["release"] == "abc1234"


def test_setup_sentry_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """main.py + celery_app.py 都会调；同进程重复调用应 short-circuit，不二次 init。"""
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://abc@example.ingest.sentry.io/1")

    with patch("app.core.sentry.sentry_sdk.init") as mocked_init:
        ok1 = sentry_mod.setup_sentry()
        ok2 = sentry_mod.setup_sentry()
        ok3 = sentry_mod.setup_sentry()

    assert ok1 is ok2 is ok3 is True
    # 三次调用，``sentry_sdk.init`` 只跑一次
    assert mocked_init.call_count == 1


def test_settings_sentry_defaults_are_pmf_friendly() -> None:
    """默认值检查：PMF 期最少噪音 / 最大合规保守。

    这些默认值是公开契约的一部分（dev 拉仓库不应该意外把 traces 全采或暴露 PII）。
    任何修改要主动评估并改本测试。

    注：直接读 ``model_fields`` 的默认值，避免被本机 ``.env.local`` 覆盖污染。
    """
    fields = settings.__class__.model_fields
    assert fields["SENTRY_DSN"].default == ""
    assert fields["SENTRY_TRACES_SAMPLE_RATE"].default == 0.0
    assert fields["SENTRY_PROFILES_SAMPLE_RATE"].default == 0.0
    assert fields["SENTRY_ENVIRONMENT"].default == ""
    assert fields["SENTRY_RELEASE"].default == ""
    assert fields["SENTRY_SEND_DEFAULT_PII"].default is False
