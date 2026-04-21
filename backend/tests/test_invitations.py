"""W7-T4：邀请裂变测试.

覆盖：
- 注册带 code → invitation 写入 + 双方 AnalysisQuota.bonus +1
- 注册 code 无效 → 正常注册，不写 invitation
- 注册 code = 自己 → 忽略
- 同一 inviter+invitee 不会重复写（幂等）
- 被邀请者首次 completed 分析 → status=valid
- 二次分析 → 不重复结算（保持 valid，不改动）
- inviter valid=5 → 发 7 天会员（membership_expires_at 延 7 天；免费用户 → monthly）
- GET /me/invitations & /me/invite-info 返回数据正确且昵称脱敏
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.analysis import AnalysisQuota, SwingAnalysis
from app.models.invitation import Invitation
from app.models.user import User
from app.services import invitation_service


async def _register(client: AsyncClient, invite_code: str | None = None) -> dict:
    body: dict = {"code": f"pytest_{uuid4().hex}"}
    if invite_code:
        body["invite_code"] = invite_code
    resp = await client.post("/v1/auth/wechat-login", json=body)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    return {
        "token": data["token"],
        "user": data["user"],
        "headers": {"Authorization": f"Bearer {data['token']}"},
    }


async def _get_user(user_id: str) -> User:
    async with AsyncSessionLocal() as db:
        u = await db.get(User, user_id)
        assert u is not None
        return u


# ==================== 绑定 ====================
@pytest.mark.asyncio
async def test_register_with_invite_code_creates_invitation_and_grants_bonus(
    client: AsyncClient,
):
    inviter = await _register(client)
    inviter_user = await _get_user(inviter["user"]["id"])

    invitee = await _register(client, invite_code=inviter_user.invite_code)

    async with AsyncSessionLocal() as db:
        # invitation 行存在
        rows = (
            await db.execute(
                select(Invitation).where(
                    Invitation.inviter_id == inviter_user.id,
                    Invitation.invitee_id == invitee["user"]["id"],
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "registered"

        # 双方本月 AnalysisQuota.bonus 都 +1
        for uid in (inviter_user.id, invitee["user"]["id"]):
            q = (
                await db.execute(
                    select(AnalysisQuota).where(AnalysisQuota.user_id == uid)
                )
            ).scalar_one_or_none()
            assert q is not None
            assert q.bonus == 1


@pytest.mark.asyncio
async def test_register_with_unknown_invite_code_is_ignored(client: AsyncClient):
    res = await _register(client, invite_code="ZZZZZZZZ")
    # 登录照常成功
    assert res["user"]["id"]
    # 没有 invitation 行
    async with AsyncSessionLocal() as db:
        count = (
            await db.execute(
                select(func.count())
                .select_from(Invitation)
                .where(Invitation.invitee_id == res["user"]["id"])
            )
        ).scalar_one()
        assert count == 0


@pytest.mark.asyncio
async def test_register_with_self_invite_code_is_ignored(client: AsyncClient):
    # 先注册，再取自己邀请码登出。再用"相同 openid + 自己 invite_code"登录应该走 login 分支
    # 这里构造方法：先注册拿到 invite_code，然后不通过 code 路径 —— 直接造一个带 invited_by_user_id=self
    # 的新用户验证 bind_on_register 防御。W7-T4 的主防御在 bind_on_register。
    r = await _register(client)
    user = await _get_user(r["user"]["id"])

    async with AsyncSessionLocal() as db:
        user_in_db = await db.get(User, user.id)
        assert user_in_db is not None
        # 人为置自己为 inviter（模拟作弊）
        user_in_db.invited_by_user_id = user_in_db.id
        await db.commit()

        result = await invitation_service.bind_on_register(
            db, invitee=user_in_db, invite_code=user_in_db.invite_code
        )
        assert result is None


@pytest.mark.asyncio
async def test_bind_is_idempotent(client: AsyncClient):
    inviter = await _register(client)
    inviter_u = await _get_user(inviter["user"]["id"])
    invitee = await _register(client, invite_code=inviter_u.invite_code)

    async with AsyncSessionLocal() as db:
        invitee_u = await db.get(User, invitee["user"]["id"])
        # 再次调用 bind_on_register 应返回已有行、不重复 +bonus
        existing = await invitation_service.bind_on_register(
            db, invitee=invitee_u, invite_code=inviter_u.invite_code
        )
        assert existing is not None
        await db.commit()

        q = (
            await db.execute(
                select(AnalysisQuota).where(AnalysisQuota.user_id == invitee_u.id)
            )
        ).scalar_one()
        assert q.bonus == 1  # 仍然只有 1


# ==================== 结算 ====================
async def _seed_completed_analysis(user_id: str, is_new: bool = True) -> str:
    """直接写一条 completed 分析并触发 settle。"""
    aid = new_id("swa")
    async with AsyncSessionLocal() as db:
        db.add(
            SwingAnalysis(
                id=aid,
                user_id=user_id,
                video_url="s3://fake/v.mp4",
                video_file_size=1024,
                camera_angle="face_on",
                club_type="driver",
                status="completed",
            )
        )
        await db.commit()
    return aid


@pytest.mark.asyncio
async def test_first_analysis_marks_invitation_valid(client: AsyncClient):
    inviter = await _register(client)
    inviter_u = await _get_user(inviter["user"]["id"])
    invitee = await _register(client, invite_code=inviter_u.invite_code)

    aid = await _seed_completed_analysis(invitee["user"]["id"])
    async with AsyncSessionLocal() as db:
        changed = await invitation_service.settle_on_first_analysis(
            db, user_id=invitee["user"]["id"], analysis_id=aid
        )
        await db.commit()
        assert changed is True

        inv = (
            await db.execute(
                select(Invitation).where(
                    Invitation.invitee_id == invitee["user"]["id"]
                )
            )
        ).scalar_one()
        assert inv.status == "valid"


@pytest.mark.asyncio
async def test_second_analysis_does_not_resettle(client: AsyncClient):
    inviter = await _register(client)
    inviter_u = await _get_user(inviter["user"]["id"])
    invitee = await _register(client, invite_code=inviter_u.invite_code)

    a1 = await _seed_completed_analysis(invitee["user"]["id"])
    async with AsyncSessionLocal() as db:
        await invitation_service.settle_on_first_analysis(
            db, user_id=invitee["user"]["id"], analysis_id=a1
        )
        await db.commit()

    a2 = await _seed_completed_analysis(invitee["user"]["id"])
    async with AsyncSessionLocal() as db:
        changed = await invitation_service.settle_on_first_analysis(
            db, user_id=invitee["user"]["id"], analysis_id=a2
        )
        assert changed is False  # 已经是 valid 状态，不会再结算


@pytest.mark.asyncio
async def test_fifth_valid_grants_7day_membership(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    # 一个 inviter 拉 5 个 invitee，每个都完成首次分析
    inviter = await _register(client)
    inviter_u = await _get_user(inviter["user"]["id"])
    assert inviter_u.membership_type == "free"

    for _ in range(5):
        invitee = await _register(client, invite_code=inviter_u.invite_code)
        aid = await _seed_completed_analysis(invitee["user"]["id"])
        async with AsyncSessionLocal() as db:
            await invitation_service.settle_on_first_analysis(
                db, user_id=invitee["user"]["id"], analysis_id=aid
            )
            await db.commit()

    # 奖励已发放
    inviter_u2 = await _get_user(inviter_u.id)
    assert inviter_u2.membership_type == "monthly"
    assert inviter_u2.membership_expires_at is not None
    now = datetime.now(UTC)
    delta = (inviter_u2.membership_expires_at - now).total_seconds()
    # 约 7 天（允许网络/DB 抖动 1 分钟内误差）
    assert abs(delta - 7 * 86400) < 120

    # invitation 表里有一行 bonus_granted=True
    async with AsyncSessionLocal() as db:
        granted = (
            await db.execute(
                select(func.count())
                .select_from(Invitation)
                .where(
                    Invitation.inviter_id == inviter_u.id,
                    Invitation.bonus_granted.is_(True),
                )
            )
        ).scalar_one()
        assert granted == 1


@pytest.mark.asyncio
async def test_reward_stacks_on_existing_membership(client: AsyncClient):
    """已是会员 → 奖励在到期日基础上 +7 天。"""
    inviter = await _register(client)
    inviter_u = await _get_user(inviter["user"]["id"])

    # 手动给 inviter 装一个 30 天的月度会员
    async with AsyncSessionLocal() as db:
        u = await db.get(User, inviter_u.id)
        u.membership_type = "monthly"
        u.membership_started_at = datetime.now(UTC)
        u.membership_expires_at = datetime.now(UTC) + timedelta(days=30)
        await db.commit()

    original_expiry = (await _get_user(inviter_u.id)).membership_expires_at
    assert original_expiry is not None

    for _ in range(5):
        invitee = await _register(client, invite_code=inviter_u.invite_code)
        aid = await _seed_completed_analysis(invitee["user"]["id"])
        async with AsyncSessionLocal() as db:
            await invitation_service.settle_on_first_analysis(
                db, user_id=invitee["user"]["id"], analysis_id=aid
            )
            await db.commit()

    new_expiry = (await _get_user(inviter_u.id)).membership_expires_at
    assert new_expiry is not None
    delta = (new_expiry - original_expiry).total_seconds()
    assert abs(delta - 7 * 86400) < 120


# ==================== API ====================
@pytest.mark.asyncio
async def test_invite_info_endpoint(client: AsyncClient):
    inviter = await _register(client)
    inviter_u = await _get_user(inviter["user"]["id"])
    # 拉 2 个，1 个 valid、1 个 registered
    inv_a = await _register(client, invite_code=inviter_u.invite_code)
    await _register(client, invite_code=inviter_u.invite_code)  # 第二个保持 registered

    aid = await _seed_completed_analysis(inv_a["user"]["id"])
    async with AsyncSessionLocal() as db:
        await invitation_service.settle_on_first_analysis(
            db, user_id=inv_a["user"]["id"], analysis_id=aid
        )
        await db.commit()

    info = (
        await client.get("/v1/users/me/invite-info", headers=inviter["headers"])
    ).json()["data"]
    assert info["invite_code"] == inviter_u.invite_code
    assert info["total_invited"] == 2
    assert info["valid_count"] == 1
    assert info["next_reward_at"] == 5
    assert info["days_to_next_reward"] == 4
    assert info["total_bonus_days"] == 0  # 还没到 5


@pytest.mark.asyncio
async def test_list_invitations_masks_nickname(client: AsyncClient):
    inviter = await _register(client)
    inviter_u = await _get_user(inviter["user"]["id"])
    invitee = await _register(client, invite_code=inviter_u.invite_code)

    # 给 invitee 设个昵称
    async with AsyncSessionLocal() as db:
        u = await db.get(User, invitee["user"]["id"])
        u.nickname = "张三丰"
        await db.commit()

    resp = await client.get("/v1/users/me/invitations", headers=inviter["headers"])
    items = resp.json()["data"]
    assert len(items) == 1
    assert items[0]["status"] == "registered"
    # "张三丰" → "张***丰"
    assert items[0]["invitee_nickname_masked"] == "张***丰"


@pytest.mark.asyncio
async def test_mask_nickname_edge_cases():
    assert invitation_service.mask_nickname(None) == "匿名球友"
    assert invitation_service.mask_nickname("") == "匿名球友"
    assert invitation_service.mask_nickname("A") == "A"
    assert invitation_service.mask_nickname("AB") == "A*"
    assert invitation_service.mask_nickname("张三丰") == "张***丰"
    assert invitation_service.mask_nickname("张无忌张翠山") == "张***山"
