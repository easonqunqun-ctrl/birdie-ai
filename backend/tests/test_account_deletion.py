"""账号注销冷静期 + 到期硬删（MVP §3.4）。

覆盖范围
--------
1. **API 入口**：申请 / 取消注销的成功路径与三类业务错误（确认文案 / 已申请 / pending 订单）。
2. **懒清理**：``get_user_by_id`` 在用户下次请求时按 ``account_deletion_scheduled_at`` 硬删。
3. **Celery beat 兜底**：``purge_due_account_deletions_task`` 即便用户不再登录也按时清理（PIPL）。
4. **Beat schedule 注册**：避免后续重构时把任务从 ``celery_app.beat_schedule`` 移除而失声。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.models.user import User


@pytest_asyncio.fixture(autouse=True)
async def _isolate_account_deletion_table() -> None:
    """模块级隔离：每个用例开始前清空所有用户的 ``account_deletion_scheduled_at``。

    动机：beat 任务 ``_purge_due_account_deletions_async`` 会扫全表清理所有到期账号，
    若上一个测试残留了 ``scheduled_at IS NOT NULL`` 的行，本测试断言精确数量时会被污染。
    本 fixture 仅清字段（不删用户），开销小；惰性清理用例可在自己 setUp 后再 set 时间。
    """
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(User)
            .where(User.account_deletion_scheduled_at.isnot(None))
            .values(account_deletion_scheduled_at=None)
        )
        await db.commit()


async def _register(client: AsyncClient) -> tuple[str, dict[str, str]]:
    """走 mock 登录拉一个新用户，返回 (user_id, auth_headers)。"""
    r = await client.post(
        "/v1/auth/wechat-login", json={"code": f"acctdel_{uuid4().hex}"}
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    return body["user"]["id"], {"Authorization": f"Bearer {body['token']}"}


async def _set_deletion_due_at(user_id: str, when: datetime) -> None:
    """直接改 ``account_deletion_scheduled_at`` 字段以便测试到期 / 已到期分支。"""
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        assert user is not None, "测试预设用户应存在"
        user.account_deletion_scheduled_at = when
        await db.commit()


# ============================================================
# API：申请 / 取消
# ============================================================


@pytest.mark.asyncio
async def test_request_account_deletion_happy_path(client: AsyncClient) -> None:
    """正常申请：返回 200 且 ``account_deletion_scheduled_at`` 落在 ~7 天后。"""
    uid, headers = await _register(client)
    before = datetime.now(UTC)
    r = await client.post(
        "/v1/users/me/account-deletion",
        json={"confirm_text": "DELETE"},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    async with AsyncSessionLocal() as db:
        user = await db.get(User, uid)
        assert user is not None
        assert user.account_deletion_scheduled_at is not None
        # 7 天冷静期：允许 1 分钟的 setUp 抖动
        expected = before + timedelta(days=7)
        delta = abs((user.account_deletion_scheduled_at - expected).total_seconds())
        assert delta < 60, f"scheduled_at 偏离 7 天 {delta}s"


@pytest.mark.asyncio
async def test_request_account_deletion_rejects_wrong_confirm_text(
    client: AsyncClient,
) -> None:
    """``confirm_text`` 非 "DELETE" 应 400 / code=40001。"""
    _, headers = await _register(client)
    r = await client.post(
        "/v1/users/me/account-deletion",
        json={"confirm_text": "delete"},  # 小写不行
        headers=headers,
    )
    assert r.status_code == 400, r.text
    assert r.json()["code"] == 40001


@pytest.mark.asyncio
async def test_request_account_deletion_idempotent_within_cooldown(
    client: AsyncClient,
) -> None:
    """已在冷静期再次申请应 400 / code=40015，避免重复"延期"。"""
    _, headers = await _register(client)
    r1 = await client.post(
        "/v1/users/me/account-deletion",
        json={"confirm_text": "DELETE"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    r2 = await client.post(
        "/v1/users/me/account-deletion",
        json={"confirm_text": "DELETE"},
        headers=headers,
    )
    assert r2.status_code == 400, r2.text
    assert r2.json()["code"] == 40015


@pytest.mark.asyncio
async def test_cancel_account_deletion_clears_schedule(client: AsyncClient) -> None:
    """取消注销：``account_deletion_scheduled_at`` 应回到 None。"""
    uid, headers = await _register(client)
    r = await client.post(
        "/v1/users/me/account-deletion",
        json={"confirm_text": "DELETE"},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    r2 = await client.post(
        "/v1/users/me/account-deletion/cancel", headers=headers
    )
    assert r2.status_code == 200, r2.text

    async with AsyncSessionLocal() as db:
        user = await db.get(User, uid)
        assert user is not None
        assert user.account_deletion_scheduled_at is None


@pytest.mark.asyncio
async def test_cancel_account_deletion_rejects_when_not_pending(
    client: AsyncClient,
) -> None:
    """未在注销状态时取消应 400。"""
    _, headers = await _register(client)
    r = await client.post(
        "/v1/users/me/account-deletion/cancel", headers=headers
    )
    assert r.status_code == 400, r.text
    assert r.json()["code"] == 40001


# ============================================================
# 懒清理：get_user_by_id 在用户请求时按期硬删
# ============================================================


@pytest.mark.asyncio
async def test_lazy_purge_on_next_request_after_due(client: AsyncClient) -> None:
    """``account_deletion_scheduled_at <= now`` 时下次 GET /users/me 应 404（用户已被清）。"""
    uid, headers = await _register(client)
    # 直接把 scheduled_at 拨到过去
    await _set_deletion_due_at(uid, datetime.now(UTC) - timedelta(minutes=1))

    r = await client.get("/v1/users/me", headers=headers)
    # `get_user_by_id` 触发硬删后抛 NotFoundError(40401, http=404)
    assert r.status_code == 404, r.text
    assert r.json()["code"] == 40401

    # 数据真的被清掉了（CASCADE）
    async with AsyncSessionLocal() as db:
        assert await db.get(User, uid) is None


@pytest.mark.asyncio
async def test_lazy_purge_skips_when_not_due(client: AsyncClient) -> None:
    """``scheduled_at`` 仍在未来时不应被硬删。"""
    uid, headers = await _register(client)
    await _set_deletion_due_at(uid, datetime.now(UTC) + timedelta(days=3))
    r = await client.get("/v1/users/me", headers=headers)
    assert r.status_code == 200, r.text

    async with AsyncSessionLocal() as db:
        user = await db.get(User, uid)
        assert user is not None
        assert user.account_deletion_scheduled_at is not None


# ============================================================
# Celery beat 兜底任务
# ============================================================


@pytest.mark.asyncio
async def test_purge_due_account_deletions_async_purges_due_users(
    client: AsyncClient,
) -> None:
    """Beat 任务：到期用户应被硬删；未到期保留；其余用户保留。"""
    uid_due, _ = await _register(client)
    uid_future, _ = await _register(client)
    uid_active, _ = await _register(client)  # 未申请注销，应保留

    await _set_deletion_due_at(uid_due, datetime.now(UTC) - timedelta(hours=1))
    await _set_deletion_due_at(
        uid_future, datetime.now(UTC) + timedelta(days=3)
    )

    from app.tasks.account_tasks import _purge_due_account_deletions_async

    purged, failed = await _purge_due_account_deletions_async()
    # autouse fixture 已隔离过 scheduled_at，所以这里能做精确断言
    assert purged == 1
    assert failed == 0

    async with AsyncSessionLocal() as db:
        assert await db.get(User, uid_due) is None, "到期用户应已被清理"
        assert await db.get(User, uid_future) is not None, "未到期用户应保留"
        assert await db.get(User, uid_active) is not None, "未申请注销的用户应保留"


@pytest.mark.asyncio
async def test_purge_due_account_deletions_async_noop_when_nothing_due(
    client: AsyncClient,
) -> None:
    """没有任何到期用户时返回 (0, 0)；保留新建活跃用户。"""
    uid, _ = await _register(client)

    from app.tasks.account_tasks import _purge_due_account_deletions_async

    purged, failed = await _purge_due_account_deletions_async()
    assert purged == 0
    assert failed == 0
    async with AsyncSessionLocal() as db:
        assert await db.get(User, uid) is not None


@pytest.mark.asyncio
async def test_purge_due_account_deletions_async_counts_failures(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``purge_user_if_due`` 抛异常时 → 计入 ``failed`` 而非 ``purged``，且不打断后续清理。"""
    uid_bad, _ = await _register(client)
    uid_ok, _ = await _register(client)
    await _set_deletion_due_at(uid_bad, datetime.now(UTC) - timedelta(hours=2))
    await _set_deletion_due_at(uid_ok, datetime.now(UTC) - timedelta(hours=1))

    from app.services import account_deletion_service
    from app.tasks import account_tasks as mod

    real_purge = account_deletion_service.purge_user_if_due

    async def flaky_purge(db, user):  # type: ignore[no-untyped-def]
        if user.id == uid_bad:
            raise RuntimeError("synthetic CASCADE failure")
        return await real_purge(db, user)

    # account_tasks 里写的是 `account_deletion_service.purge_user_if_due`，patch 源模块即可
    monkeypatch.setattr(
        account_deletion_service, "purge_user_if_due", flaky_purge
    )
    # account_tasks 模块内通过 `from app.services import account_deletion_service`
    # 引用，monkeypatch 源模块属性已能生效（不是 `from ... import ...` 的 name binding）

    purged, failed = await mod._purge_due_account_deletions_async()
    assert purged == 1
    assert failed == 1

    async with AsyncSessionLocal() as db:
        # 失败的 user 仍在表里（说明异常被吞掉、scheduled_at 也没改）
        assert await db.get(User, uid_bad) is not None
        assert await db.get(User, uid_ok) is None


# ============================================================
# Beat 注册防回归
# ============================================================


def test_purge_due_account_deletions_in_beat_schedule() -> None:
    """celery_app.beat_schedule 必须挂上账号注销清理任务（防止重构时静默丢失）。"""
    from app.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule or {}
    assert "purge-due-account-deletions" in schedule, (
        "MVP §3.4 PIPL 合规依赖此 beat；不要从 beat_schedule 里移除"
    )
    entry = schedule["purge-due-account-deletions"]
    assert entry["task"] == "xiaoniao.purge_due_account_deletions"


def test_purge_due_account_deletions_task_registered() -> None:
    """Celery worker 应已注册 ``xiaoniao.purge_due_account_deletions``。"""
    # 让 task 被 import；测试运行时只 import celery_app 不一定 trigger include 链
    from app.tasks import account_tasks  # noqa: F401
    from app.celery_app import celery_app

    assert "xiaoniao.purge_due_account_deletions" in celery_app.tasks
