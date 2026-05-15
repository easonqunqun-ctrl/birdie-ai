"""W8-T3：QUOTA_MODE=unlimited 模式行为测试。

验证当 settings.QUOTA_MODE 切到 `unlimited` 时：
  1. 新建免费用户的分析 / 对话配额记录 total = -1
  2. /users/me 返回 analysis_remaining / chat_remaining_today / *_total 都 = -1
  3. consume / check 在已存在 quota.total>=0 的旧用户身上仍按旧记录扣减
     （unlimited 仅影响"新建"时的 total；不主动改写既存记录，避免破坏会员逻辑）
  4. 切回 strict 后新用户回到 3 / 5 默认值
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.config import settings


@pytest_asyncio.fixture
async def quota_unlimited(monkeypatch: pytest.MonkeyPatch) -> None:
    """打开 QUOTA_MODE=unlimited（仅本测试生效，自动还原）."""
    monkeypatch.setattr(settings, "QUOTA_MODE", "unlimited")


@pytest.mark.asyncio
async def test_unlimited_mode_new_user_gets_minus_one_quota(
    client: AsyncClient,
    auth_headers: dict[str, str],
    quota_unlimited: None,
):
    """unlimited 模式下，新用户首次拉 /me 应得到 -1 配额（前端 < 0 即无限）."""
    resp = await client.get("/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    quota = resp.json()["data"]["quota"]
    assert quota["analysis_remaining"] == -1
    assert quota["analysis_total"] == -1
    assert quota["chat_remaining_today"] == -1
    assert quota["chat_total_today"] == -1


@pytest.mark.asyncio
async def test_unlimited_mode_consume_does_not_block(
    client: AsyncClient,
    auth_headers: dict[str, str],
    quota_unlimited: None,
):
    """unlimited 模式下连发多次分析也不会被卡（remaining 永远是 -1）."""
    # 拉一次 /me 触发配额初始化
    await client.get("/v1/users/me", headers=auth_headers)

    # 连续 5 次（远超 strict 模式下的 3 次月限）申请上传凭证，应全部 200
    for _ in range(5):
        resp = await client.post(
            "/v1/analyses/upload-token",
            headers=auth_headers,
            json={
                "file_name": "swing.mp4",
                "file_size": 1024 * 1024,
                "file_type": "video/mp4",
                "duration": 8.0,
            },
        )
        assert resp.status_code == 200, resp.text

    # 拉 /me 再确认 remaining 仍为 -1
    me = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me["quota"]["analysis_remaining"] == -1


@pytest.mark.asyncio
async def test_strict_mode_default_still_returns_3_5(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """对照组：默认 strict 模式下，新免费用户拿到 3 / 5（防 unlimited 改动污染默认行为）."""
    assert settings.QUOTA_MODE == "strict"
    resp = await client.get("/v1/users/me", headers=auth_headers)
    quota = resp.json()["data"]["quota"]
    assert quota["analysis_remaining"] == 3
    assert quota["analysis_total"] == 3
    assert quota["chat_remaining_today"] == 5
    assert quota["chat_total_today"] == 5


@pytest.mark.asyncio
async def test_unlimited_does_not_overwrite_existing_strict_quota(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    """先在 strict 下创出 total=3 的记录，再切到 unlimited——
    既存记录不会被自动改写（设计取舍：避免引入"配额迁移"逻辑），
    新逻辑只对"还没建过当月/当日记录的用户"生效。
    """
    # strict 模式：先初始化记录
    me1 = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    assert me1["quota"]["analysis_remaining"] == 3

    # 切 unlimited
    monkeypatch.setattr(settings, "QUOTA_MODE", "unlimited")
    me2 = (await client.get("/v1/users/me", headers=auth_headers)).json()["data"]
    # 既有记录 total=3 没动，所以 remaining 仍是 3（不是 -1）
    # 这是 W8-T3 已知约束：内测期请确保部署时初始化的是空库
    assert me2["quota"]["analysis_remaining"] == 3
