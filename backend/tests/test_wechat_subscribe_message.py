"""subscribeMessage.send 分析完成：开关与 mock 跳过逻辑。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config import settings


@pytest.mark.asyncio
async def test_send_analysis_completed_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_MESSAGE_ENABLED", False)
    from app.integrations.wechat_subscribe_message import send_analysis_completed_notification

    await send_analysis_completed_notification(
        openid="oABC",
        analysis_id="ana_test",
        overall_score=82,
        analyzed_at=datetime(2026, 5, 20, 10, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_send_analysis_completed_skips_mock_login_openid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_MESSAGE_ENABLED", True)
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_ANALYSIS_TEMPLATE_ID", "tpl_xx")
    monkeypatch.setattr(settings, "WECHAT_MOCK_LOGIN", True)
    from app.integrations.wechat_subscribe_message import send_analysis_completed_notification

    await send_analysis_completed_notification(
        openid="mock_openid_xx",
        analysis_id="ana_test",
        overall_score=82,
        analyzed_at=None,
    )


@pytest.mark.asyncio
async def test_send_membership_expired_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_MESSAGE_ENABLED", False)
    from app.integrations.wechat_subscribe_message import send_membership_expired_notification

    await send_membership_expired_notification(
        openid="oABC",
        expired_at=datetime(2026, 5, 20, 10, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_send_membership_expired_skips_mock_login_openid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_MESSAGE_ENABLED", True)
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_MEMBERSHIP_EXPIRE_TEMPLATE_ID", "tpl_member")
    monkeypatch.setattr(settings, "WECHAT_MOCK_LOGIN", True)
    from app.integrations.wechat_subscribe_message import send_membership_expired_notification

    await send_membership_expired_notification(
        openid="oReal",
        expired_at=datetime(2026, 5, 20, 10, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_send_membership_expired_noop_when_template_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_MESSAGE_ENABLED", True)
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_MEMBERSHIP_EXPIRE_TEMPLATE_ID", "")
    monkeypatch.setattr(settings, "WECHAT_MOCK_LOGIN", False)
    from app.integrations.wechat_subscribe_message import send_membership_expired_notification

    await send_membership_expired_notification(
        openid="oReal",
        expired_at=datetime(2026, 5, 20, 10, 0, tzinfo=UTC),
    )
