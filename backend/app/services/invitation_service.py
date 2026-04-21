"""邀请裂变服务（W7-T4）.

核心场景：

1. **注册时绑定邀请**（`bind_on_register`）：
   - `login_or_create_user` 已经把 `invited_by_user_id` 写到 `users` 表；
     这里只负责**在 invitations 表里插一条记录**并给双方各 +1 次当月分析配额
   - 防作弊：code = 自己 / 已经有 inviter 的用户再次登录都不重复写（UniqueConstraint 保底）

2. **被邀请者完成首次分析**（`settle_on_first_analysis`）：
   - 由 `app.tasks.analysis_tasks._mark_completed` 的成功分支调用
   - 若 invitee 只有这一条 completed 分析 → 把对应 invitation 的 status 升为 valid
   - 若升 valid 后 inviter 累计 valid 数刚好达到 `INVITATION_REWARD_THRESHOLD=5`：
     发 `INVITATION_REWARD_MEMBERSHIP_DAYS=7` 天会员；标记 bonus_granted

3. **查询**（`list_my_invitations` / `get_invite_info`）：邀请记录页 + 概览卡

注意：
- 注册期的 +1 分析 bonus 是**一次性 + 当月配额**；配额按月重置后自然消失（docs/01 §4.2）
- 会员 7 天奖励：与订单续期类似，未过期则叠加到原到期日；免费用户则设为 monthly + 7 天
- 整个服务都不自己 commit —— 调用方负责事务边界（保持和 payment_service 一致）
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.models.invitation import Invitation
from app.models.user import User
from app.services import quota_service

# ============================================================
# 业务常量（docs/01 §7.3 + §8.2）
# ============================================================
INVITATION_SIGNUP_BONUS_ANALYSES = 1  # 注册后双方各 +1 次当月分析
INVITATION_REWARD_THRESHOLD = 5  # 累计 N 个 valid 触发奖励
INVITATION_REWARD_MEMBERSHIP_DAYS = 7  # 奖励：+7 天会员


# ============================================================
# 注册时绑定
# ============================================================
async def bind_on_register(
    db: AsyncSession,
    *,
    invitee: User,
    invite_code: str,
) -> Invitation | None:
    """新用户注册时调用；返回创建的 Invitation 或 None（无效/重复）。

    逻辑：
    - `login_or_create_user` 已经尝试把 `invited_by_user_id` 写好；这里再用那个字段查 inviter
    - 若没有匹配的 inviter（code 无效 / code = 自己） → 返回 None（不抛错）
    - 若已经有 invitation → 返回 None（幂等）
    - 否则插入 invitation + 给双方当月 AnalysisQuota.bonus += 1
    """
    if not invitee.invited_by_user_id:
        return None
    if invitee.invited_by_user_id == invitee.id:
        return None  # 自我邀请（理论上 login_or_create 阶段已经拦下，这里防御）

    inviter = await db.get(User, invitee.invited_by_user_id)
    if inviter is None:
        return None

    # 防重复（unique(inviter_id, invitee_id)）：先查
    existing = (
        await db.execute(
            select(Invitation).where(
                Invitation.inviter_id == inviter.id,
                Invitation.invitee_id == invitee.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    invitation = Invitation(
        id=new_id("inv"),
        inviter_id=inviter.id,
        invitee_id=invitee.id,
        invite_code=inviter.invite_code,
        status="registered",
    )
    db.add(invitation)
    await db.flush()

    # 双方 +1 分析 bonus（当月）
    for u in (inviter, invitee):
        quota = await quota_service.get_or_create_analysis_quota(db, u)
        assert quota is not None
        quota.bonus = (quota.bonus or 0) + INVITATION_SIGNUP_BONUS_ANALYSES

    await db.flush()
    return invitation


# ============================================================
# 被邀请者完成首次分析 → 结算
# ============================================================
async def settle_on_first_analysis(
    db: AsyncSession,
    *,
    user_id: str,
    analysis_id: str,
) -> bool:
    """在 `_mark_completed` 里调用；若触发了 invitation 升级 valid 则返回 True。

    幂等：同一个 user_id 二次及以后进来都不会重复结算（用"是否 registered"判断）。
    """
    # 查这个用户是否是某个人的 invitee
    stmt = select(Invitation).where(
        Invitation.invitee_id == user_id,
        Invitation.status == "registered",
    )
    invitation = (await db.execute(stmt)).scalar_one_or_none()
    if invitation is None:
        return False

    # 判断这是否是"首次"完成的分析：
    # 即除 analysis_id 之外，该用户是否还有其他 completed 分析
    count_stmt = select(func.count()).where(
        SwingAnalysis.user_id == user_id,
        SwingAnalysis.status == "completed",
        SwingAnalysis.id != analysis_id,
    )
    prev_completed = (await db.execute(count_stmt)).scalar_one()
    if prev_completed > 0:
        # 不是首次 → 不结算（也不应该发生，因为 status=registered 意味着从未结算过；
        # 但为了防御重跑历史数据，保守处理）
        return False

    invitation.status = "valid"
    await db.flush()

    # 检查 inviter valid 计数是否够奖励
    await _maybe_grant_reward(db, inviter_id=invitation.inviter_id)
    return True


async def _maybe_grant_reward(db: AsyncSession, *, inviter_id: str) -> None:
    """若 inviter 累计 valid 数达到未发放的阈值 → 发会员天数奖励。

    W7 实现简化版：只做 5 人一档（+7 天）。`invitations.bonus_granted` 标记
    哪条 invitation 记录对应这次奖励（用第 N 条 valid 的记录存放）。
    """
    valid_count = (
        await db.execute(
            select(func.count())
            .select_from(Invitation)
            .where(
                Invitation.inviter_id == inviter_id,
                Invitation.status == "valid",
            )
        )
    ).scalar_one()

    if valid_count < INVITATION_REWARD_THRESHOLD:
        return

    # 若已发放过（本档），跳过
    already_granted = (
        await db.execute(
            select(func.count())
            .select_from(Invitation)
            .where(
                Invitation.inviter_id == inviter_id,
                Invitation.bonus_granted.is_(True),
                Invitation.inviter_bonus_type == "membership_days",
            )
        )
    ).scalar_one()
    if already_granted >= valid_count // INVITATION_REWARD_THRESHOLD:
        return  # W7 每 5 人只发一次；更高档延后

    # 取最近一条 valid 且未标记的 invitation 做奖励凭证
    pending = (
        await db.execute(
            select(Invitation)
            .where(
                Invitation.inviter_id == inviter_id,
                Invitation.status == "valid",
                Invitation.bonus_granted.is_(False),
            )
            .order_by(Invitation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if pending is None:
        return

    inviter = await db.get(User, inviter_id)
    if inviter is None:
        return

    now = datetime.now(UTC)
    base = inviter.membership_expires_at
    if base is None or base <= now:
        base = now
        inviter.membership_started_at = now
        # 免费用户首次获得 → 升 monthly
        if inviter.membership_type == "free":
            inviter.membership_type = "monthly"
    inviter.membership_expires_at = base + timedelta(
        days=INVITATION_REWARD_MEMBERSHIP_DAYS
    )

    pending.bonus_granted = True
    pending.bonus_granted_at = now
    pending.inviter_bonus_type = "membership_days"
    pending.inviter_bonus_amount = INVITATION_REWARD_MEMBERSHIP_DAYS

    await db.flush()


# ============================================================
# 查询
# ============================================================
async def list_my_invitations(
    db: AsyncSession, inviter: User
) -> list[tuple[Invitation, User]]:
    """返回 [(invitation, invitee_user), ...]，按时间倒序。"""
    stmt = (
        select(Invitation, User)
        .join(User, User.id == Invitation.invitee_id)
        .where(Invitation.inviter_id == inviter.id)
        .order_by(Invitation.created_at.desc())
    )
    return list((await db.execute(stmt)).all())


async def get_invite_overview(db: AsyncSession, inviter: User) -> dict:
    """邀请概览（给邀请页顶部卡用）."""
    total = (
        await db.execute(
            select(func.count()).select_from(Invitation).where(
                Invitation.inviter_id == inviter.id
            )
        )
    ).scalar_one()
    valid = (
        await db.execute(
            select(func.count())
            .select_from(Invitation)
            .where(
                Invitation.inviter_id == inviter.id,
                Invitation.status == "valid",
            )
        )
    ).scalar_one()
    total_bonus = (
        await db.execute(
            select(func.coalesce(func.sum(Invitation.inviter_bonus_amount), 0))
            .select_from(Invitation)
            .where(
                Invitation.inviter_id == inviter.id,
                Invitation.bonus_granted.is_(True),
                Invitation.inviter_bonus_type == "membership_days",
            )
        )
    ).scalar_one()

    # 下一档：5 人 / 10 人 / 15 人...；W7 先做 5
    next_threshold = (
        (valid // INVITATION_REWARD_THRESHOLD) + 1
    ) * INVITATION_REWARD_THRESHOLD
    days_to_next = max(0, next_threshold - valid)

    return {
        "invite_code": inviter.invite_code,
        "total_invited": total,
        "valid_count": valid,
        "next_reward_at": next_threshold,
        "days_to_next_reward": days_to_next,
        "total_bonus_days": int(total_bonus),
    }


# ============================================================
# 脱敏
# ============================================================
def mask_nickname(nickname: str | None) -> str:
    """昵称脱敏：保留首尾 1 个字，中间用 *** 替换。空/过短 → "匿名球友"。"""
    if not nickname:
        return "匿名球友"
    n = nickname.strip()
    if len(n) <= 1:
        return n
    if len(n) == 2:
        return n[0] + "*"
    return n[0] + "***" + n[-1]
