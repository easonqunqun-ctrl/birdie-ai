"""用户服务：登录、查询、更新."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import new_id, new_invite_code
from app.integrations.wechat import WechatSession
from app.models.user import User


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError(code=40401, message="用户不存在")
    # W7-T1：会员到期惰性降级。调用方（含 get_current_user）所在的请求事务会
    # 在响应阶段 commit；降级 UPDATE 随请求一起落库，无需额外 flush。
    # 循环导入规避：在函数内 import
    from app.services import payment_service

    await payment_service.ensure_membership_valid(db, user)
    return user


async def get_user_by_openid(db: AsyncSession, openid: str) -> User | None:
    stmt = select(User).where(User.wechat_openid == openid, User.deleted_at.is_(None))
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_invite_code(db: AsyncSession, invite_code: str) -> User | None:
    stmt = select(User).where(User.invite_code == invite_code, User.deleted_at.is_(None))
    return (await db.execute(stmt)).scalar_one_or_none()


async def login_or_create_user(
    db: AsyncSession,
    wechat: WechatSession,
    invite_code: str | None = None,
) -> tuple[User, bool]:
    """微信登录入口：找到用户则返回，否则创建新用户。返回 (user, is_new_user)."""
    user = await get_user_by_openid(db, wechat.openid)
    if user is not None:
        user.last_login_at = datetime.now(UTC)
        await db.flush()
        return user, False

    inviter_id: str | None = None
    if invite_code:
        inviter = await get_user_by_invite_code(db, invite_code)
        if inviter is not None:
            inviter_id = inviter.id

    user = User(
        id=new_id("usr"),
        wechat_openid=wechat.openid,
        wechat_unionid=wechat.unionid,
        nickname=None,
        avatar_url=None,
        invite_code=await _gen_unique_invite_code(db),
        invited_by_user_id=inviter_id,
        membership_type="free",
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()

    # W7-T4：若带了有效 invite_code → 写 invitations 表 + 给双方 +1 当月分析 bonus。
    # 循环导入规避：函数内 import。
    if inviter_id is not None and invite_code:
        from app.services import invitation_service

        await invitation_service.bind_on_register(
            db, invitee=user, invite_code=invite_code
        )

    return user, True


async def _gen_unique_invite_code(db: AsyncSession, max_attempts: int = 5) -> str:
    """生成全局唯一的邀请码."""
    for _ in range(max_attempts):
        code = new_invite_code()
        existing = await get_user_by_invite_code(db, code)
        if existing is None:
            return code
    raise RuntimeError("无法生成唯一邀请码")
