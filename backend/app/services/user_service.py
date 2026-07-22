"""用户服务：登录、查询、更新."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.security import new_id, new_invite_code
from app.integrations.apple_auth import AppleIdentity
from app.integrations.wechat import WechatAppOAuthSession, WechatSession
from app.models.user import User

logger = get_logger("user_service")


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError(code=40401, message="用户不存在")
    if (
        user.account_deletion_scheduled_at is not None
        and user.account_deletion_scheduled_at <= datetime.now(UTC)
    ):
        from app.services import account_deletion_service

        if await account_deletion_service.purge_user_if_due(db, user):
            raise NotFoundError(code=40401, message="用户不存在")
    # W7-T1：会员到期惰性降级。调用方（含 get_current_user）所在的请求事务会
    # 在响应阶段 commit；降级 UPDATE 随请求一起落库，无需额外 flush。
    # 循环导入规避：在函数内 import
    from app.services import payment_service

    await payment_service.ensure_membership_valid(db, user)
    return user


async def get_user_by_minipro_openid(db: AsyncSession, openid: str) -> User | None:
    stmt = select(User).where(User.wechat_openid == openid, User.deleted_at.is_(None))
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_app_openid(db: AsyncSession, app_openid: str) -> User | None:
    stmt = select(User).where(
        User.wechat_app_openid == app_openid, User.deleted_at.is_(None)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_apple_sub(db: AsyncSession, apple_sub: str) -> User | None:
    stmt = select(User).where(User.apple_sub == apple_sub, User.deleted_at.is_(None))
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_unionid(db: AsyncSession, unionid: str) -> User | None:
    stmt = select(User).where(
        User.wechat_unionid == unionid,
        User.deleted_at.is_(None),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_invite_code(db: AsyncSession, invite_code: str) -> User | None:
    stmt = select(User).where(User.invite_code == invite_code, User.deleted_at.is_(None))
    return (await db.execute(stmt)).scalar_one_or_none()


async def _sync_bind_invitations(
    db: AsyncSession, user: User, invite_code: str | None, inviter_id: str | None
) -> None:
    """新用户建档后写入邀请裂变（与旧逻辑等价）。"""
    if inviter_id is not None and invite_code:
        from app.services import invitation_service

        await invitation_service.bind_on_register(db, invitee=user, invite_code=invite_code)


async def login_or_create_user(
    db: AsyncSession,
    wechat: WechatSession,
    invite_code: str | None = None,
) -> tuple[User, bool]:
    """微信小程序登录入口：unionid → 小程序 openid 依次命中；必要时合并字段。"""
    user: User | None = None
    if wechat.unionid:
        user = await get_user_by_unionid(db, wechat.unionid)
    if user is None:
        user = await get_user_by_minipro_openid(db, wechat.openid)
    inviter_id: str | None = None
    if invite_code:
        inviter = await get_user_by_invite_code(db, invite_code)
        if inviter is not None:
            inviter_id = inviter.id

    if user is not None:
        user.last_login_at = datetime.now(UTC)
        if wechat.unionid and user.wechat_unionid is None:
            user.wechat_unionid = wechat.unionid
        if user.wechat_openid != wechat.openid:
            if user.wechat_openid is None:
                user.wechat_openid = wechat.openid
            elif wechat.unionid and user.wechat_unionid == wechat.unionid:
                # unionid 对齐后允许「旧数据只有 App 帐号」回填小程序侧 openid。
                logger.warning(
                    "wechat_mini_openid_mismatch_but_union_aligned",
                    user_id=user.id,
                )
                user.wechat_openid = wechat.openid
            else:
                logger.error(
                    "wechat_mini_openid_conflict_skip_overwrite",
                    user_id=user.id,
                )
        await db.flush()
        return user, False

    user = User(
        id=new_id("usr"),
        wechat_openid=wechat.openid,
        wechat_app_openid=None,
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
    await _sync_bind_invitations(db, user, invite_code, inviter_id)
    return user, True


async def login_or_create_user_app_oauth(
    db: AsyncSession,
    oauth: WechatAppOAuthSession,
    invite_code: str | None = None,
) -> tuple[User, bool]:
    """RN / 开放平台移动应用 OAuth 登录：unionid → App openid；必要时报错冲突。"""
    user: User | None = None
    if oauth.unionid:
        user = await get_user_by_unionid(db, oauth.unionid)
    if user is None:
        user = await get_user_by_app_openid(db, oauth.app_openid)

    inviter_id: str | None = None
    if invite_code:
        inviter = await get_user_by_invite_code(db, invite_code)
        if inviter is not None:
            inviter_id = inviter.id

    if user is not None:
        user.last_login_at = datetime.now(UTC)
        if oauth.unionid and user.wechat_unionid is None:
            user.wechat_unionid = oauth.unionid
        if user.wechat_app_openid != oauth.app_openid:
            if user.wechat_app_openid is None:
                user.wechat_app_openid = oauth.app_openid
            elif oauth.unionid and user.wechat_unionid == oauth.unionid:
                logger.warning(
                    "wechat_app_openid_mismatch_but_union_aligned",
                    user_id=user.id,
                )
                user.wechat_app_openid = oauth.app_openid
            else:
                logger.error(
                    "wechat_app_openid_conflict_skip_overwrite",
                    user_id=user.id,
                )
        await db.flush()
        return user, False

    user = User(
        id=new_id("usr"),
        wechat_openid=None,
        wechat_app_openid=oauth.app_openid,
        wechat_unionid=oauth.unionid,
        nickname=None,
        avatar_url=None,
        invite_code=await _gen_unique_invite_code(db),
        invited_by_user_id=inviter_id,
        membership_type="free",
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()
    await _sync_bind_invitations(db, user, invite_code, inviter_id)
    return user, True


async def login_or_create_user_apple(
    db: AsyncSession,
    identity: AppleIdentity,
    invite_code: str | None = None,
    *,
    full_name: str | None = None,
) -> tuple[User, bool]:
    """Sign in with Apple：按 `sub` 查找或创建；可选写入首次授权昵称."""
    user = await get_user_by_apple_sub(db, identity.sub)

    inviter_id: str | None = None
    if invite_code:
        inviter = await get_user_by_invite_code(db, invite_code)
        if inviter is not None:
            inviter_id = inviter.id

    if user is not None:
        user.last_login_at = datetime.now(UTC)
        if full_name and not user.nickname:
            user.nickname = full_name[:48]
        await db.flush()
        return user, False

    nickname = (full_name or "").strip()[:48] or None
    user = User(
        id=new_id("usr"),
        wechat_openid=None,
        wechat_app_openid=None,
        wechat_unionid=None,
        apple_sub=identity.sub,
        nickname=nickname,
        avatar_url=None,
        invite_code=await _gen_unique_invite_code(db),
        invited_by_user_id=inviter_id,
        membership_type="free",
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()
    await _sync_bind_invitations(db, user, invite_code, inviter_id)
    return user, True


async def _gen_unique_invite_code(db: AsyncSession, max_attempts: int = 5) -> str:
    """生成全局唯一的邀请码."""
    for _ in range(max_attempts):
        code = new_invite_code()
        existing = await get_user_by_invite_code(db, code)
        if existing is None:
            return code
    raise RuntimeError("无法生成唯一邀请码")
