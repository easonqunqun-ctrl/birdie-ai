"""Celery 支付侧任务：到期前提醒等."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import settings


class _FakeRedis:
    def __init__(self) -> None:
        self._keys: set[str] = set()

    async def set(self, key: str, val: str, *, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self._keys:
            return False
        self._keys.add(key)
        return True


@pytest.mark.asyncio
async def test_membership_pre_expiry_notify_sends_on_matching_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """上海日历剩余天数 = MEMBERSHIP_PRE_EXPIRY_NOTIFY_DAYS 时下发一次（Redis 去重）。"""
    fixed_now = datetime(2026, 5, 15, 4, 0, tzinfo=UTC)  # 上海 5/15 中午附近
    expires_at = datetime(2026, 5, 18, 10, 0, tzinfo=UTC)  # 剩余 3 天

    monkeypatch.setattr(settings, "MEMBERSHIP_PRE_EXPIRY_NOTIFY_DAYS", 3)
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_MESSAGE_ENABLED", True)
    monkeypatch.setattr(
        settings,
        "WECHAT_SUBSCRIBE_MEMBERSHIP_PRE_EXPIRE_TEMPLATE_ID",
        "tpl_pre_expire",
    )
    monkeypatch.setattr(settings, "WECHAT_MOCK_LOGIN", False)

    class _FixedDatetime:
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr("app.tasks.payment_tasks.datetime", _FixedDatetime)

    user = SimpleNamespace(
        id="usr_preexp",
        membership_type="monthly",
        membership_expires_at=expires_at,
        deleted_at=None,
        wechat_openid="oPreExp123",
    )

    sent: list[tuple[str, datetime]] = []

    async def _fake_send(*, openid: str | None, expires_at: datetime) -> None:
        assert openid
        sent.append((openid, expires_at))

    monkeypatch.setattr(
        "app.tasks.payment_tasks.send_membership_pre_expiry_notification",
        _fake_send,
    )
    monkeypatch.setattr(
        "app.tasks.payment_tasks.get_redis",
        AsyncMock(return_value=_FakeRedis()),
    )

    async def _fake_execute(_stmt):
        class _R:
            def scalars(self):
                return self

            def all(self):
                return [user]

        return _R()

    class _FakeSession:
        async def execute(self, stmt):
            return await _fake_execute(stmt)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(
        "app.tasks.payment_tasks.AsyncSessionLocal",
        lambda: _FakeSession(),
    )

    from app.tasks.payment_tasks import _membership_pre_expiry_notify_async

    n = await _membership_pre_expiry_notify_async()
    assert n == 1
    assert len(sent) == 1
    assert sent[0][0] == "oPreExp123"


@pytest.mark.asyncio
async def test_membership_pre_expiry_notify_skips_wrong_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 5, 15, 4, 0, tzinfo=UTC)
    expires_at = datetime(2026, 5, 20, 10, 0, tzinfo=UTC)  # 剩余 5 天，非 3

    monkeypatch.setattr(settings, "MEMBERSHIP_PRE_EXPIRY_NOTIFY_DAYS", 3)
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_MESSAGE_ENABLED", True)
    monkeypatch.setattr(
        settings,
        "WECHAT_SUBSCRIBE_MEMBERSHIP_PRE_EXPIRE_TEMPLATE_ID",
        "tpl_pre_expire",
    )

    class _FixedDatetime:
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr("app.tasks.payment_tasks.datetime", _FixedDatetime)

    user = SimpleNamespace(
        id="usr_skip",
        membership_type="monthly",
        membership_expires_at=expires_at,
        deleted_at=None,
        wechat_openid="oSkip",
    )

    async def _fake_send(**_kwargs):
        raise AssertionError("should not send")

    monkeypatch.setattr(
        "app.tasks.payment_tasks.send_membership_pre_expiry_notification",
        _fake_send,
    )
    monkeypatch.setattr(
        "app.tasks.payment_tasks.get_redis",
        AsyncMock(return_value=_FakeRedis()),
    )

    async def _fake_execute(_stmt):
        class _R:
            def scalars(self):
                return self

            def all(self):
                return [user]

        return _R()

    class _FakeSession:
        async def execute(self, stmt):
            return await _fake_execute(stmt)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(
        "app.tasks.payment_tasks.AsyncSessionLocal",
        lambda: _FakeSession(),
    )

    from app.tasks.payment_tasks import _membership_pre_expiry_notify_async

    n = await _membership_pre_expiry_notify_async()
    assert n == 0


@pytest.mark.asyncio
async def test_membership_pre_expiry_notify_noop_when_days_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MEMBERSHIP_PRE_EXPIRY_NOTIFY_DAYS", "0")
    from app.tasks.payment_tasks import _membership_pre_expiry_notify_async

    assert await _membership_pre_expiry_notify_async() == 0


def test_parse_notify_days_supports_csv_and_legacy_single() -> None:
    """csv 多档 + 单档 + 脏数据兜底 + 上限 8 档（产品 §3.5）。"""
    from app.tasks.payment_tasks import _parse_notify_days

    assert _parse_notify_days("7,3,1") == [1, 3, 7]
    assert _parse_notify_days("3") == [3]
    assert _parse_notify_days(3) == [3]
    assert _parse_notify_days("") == []
    assert _parse_notify_days("0") == []
    assert _parse_notify_days(None) == []
    assert _parse_notify_days("foo,3, ,bar,-1") == [3]
    assert _parse_notify_days("1,2,3,4,5,6,7,8,9,10") == [1, 2, 3, 4, 5, 6, 7, 8]


@pytest.mark.asyncio
async def test_membership_pre_expiry_notify_multi_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """多档 ``"7,3,1"``：单用户在剩余 3 天那天命中，剩余 5 天那天不命中。"""
    fixed_now = datetime(2026, 5, 15, 4, 0, tzinfo=UTC)
    expires_at = datetime(2026, 5, 18, 10, 0, tzinfo=UTC)  # 剩余 3 天 ∈ {7,3,1}

    monkeypatch.setattr(settings, "MEMBERSHIP_PRE_EXPIRY_NOTIFY_DAYS", "7,3,1")
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_MESSAGE_ENABLED", True)
    monkeypatch.setattr(
        settings, "WECHAT_SUBSCRIBE_MEMBERSHIP_PRE_EXPIRE_TEMPLATE_ID", "tpl_pre_expire"
    )
    monkeypatch.setattr(settings, "WECHAT_MOCK_LOGIN", False)

    class _FixedDatetime:
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr("app.tasks.payment_tasks.datetime", _FixedDatetime)

    user = SimpleNamespace(
        id="usr_multi",
        membership_type="monthly",
        membership_expires_at=expires_at,
        deleted_at=None,
        wechat_openid="oMulti",
    )

    sent: list[tuple[str, datetime]] = []

    async def _fake_send(*, openid: str | None, expires_at: datetime) -> None:
        sent.append((openid, expires_at))

    monkeypatch.setattr(
        "app.tasks.payment_tasks.send_membership_pre_expiry_notification", _fake_send
    )
    monkeypatch.setattr(
        "app.tasks.payment_tasks.get_redis", AsyncMock(return_value=_FakeRedis())
    )

    async def _fake_execute(_stmt):
        class _R:
            def scalars(self):
                return self

            def all(self):
                return [user]

        return _R()

    class _FakeSession:
        async def execute(self, stmt):
            return await _fake_execute(stmt)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(
        "app.tasks.payment_tasks.AsyncSessionLocal", lambda: _FakeSession()
    )

    from app.tasks.payment_tasks import _membership_pre_expiry_notify_async

    n = await _membership_pre_expiry_notify_async()
    assert n == 1
    assert sent == [("oMulti", expires_at)]


@pytest.mark.asyncio
async def test_membership_pre_expiry_notify_multi_window_per_day_dedup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一天同一档同一用户重复扫描不会再次发送（Redis nx 去重，多档独立 key）。"""
    fixed_now = datetime(2026, 5, 15, 4, 0, tzinfo=UTC)
    expires_at = datetime(2026, 5, 18, 10, 0, tzinfo=UTC)  # 剩余 3 天

    monkeypatch.setattr(settings, "MEMBERSHIP_PRE_EXPIRY_NOTIFY_DAYS", "7,3,1")
    monkeypatch.setattr(settings, "WECHAT_SUBSCRIBE_MESSAGE_ENABLED", True)
    monkeypatch.setattr(
        settings, "WECHAT_SUBSCRIBE_MEMBERSHIP_PRE_EXPIRE_TEMPLATE_ID", "tpl_pre_expire"
    )
    monkeypatch.setattr(settings, "WECHAT_MOCK_LOGIN", False)

    class _FixedDatetime:
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr("app.tasks.payment_tasks.datetime", _FixedDatetime)

    user = SimpleNamespace(
        id="usr_dup",
        membership_type="monthly",
        membership_expires_at=expires_at,
        deleted_at=None,
        wechat_openid="oDup",
    )

    sent_count = {"n": 0}

    async def _fake_send(*, openid: str | None, expires_at: datetime) -> None:
        sent_count["n"] += 1

    monkeypatch.setattr(
        "app.tasks.payment_tasks.send_membership_pre_expiry_notification", _fake_send
    )

    shared_redis = _FakeRedis()
    monkeypatch.setattr(
        "app.tasks.payment_tasks.get_redis", AsyncMock(return_value=shared_redis)
    )

    async def _fake_execute(_stmt):
        class _R:
            def scalars(self):
                return self

            def all(self):
                return [user]

        return _R()

    class _FakeSession:
        async def execute(self, stmt):
            return await _fake_execute(stmt)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(
        "app.tasks.payment_tasks.AsyncSessionLocal", lambda: _FakeSession()
    )

    from app.tasks.payment_tasks import _membership_pre_expiry_notify_async

    n1 = await _membership_pre_expiry_notify_async()
    n2 = await _membership_pre_expiry_notify_async()
    assert n1 == 1
    assert n2 == 0  # 第二轮被 Redis nx 拒绝
    assert sent_count["n"] == 1
