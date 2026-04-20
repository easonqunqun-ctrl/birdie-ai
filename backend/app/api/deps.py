"""API 层的依赖注入：当前用户、可选用户."""

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import User
from app.services.user_service import get_user_by_id


async def get_token_payload(
    authorization: str | None = Header(default=None),
) -> dict:
    """解析 Bearer Token。无 Token 或解析失败抛 UnauthorizedError."""
    if not authorization:
        raise UnauthorizedError(code=40101, message="Token 缺失")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError(code=40102, message="Token 格式错误")
    return decode_access_token(parts[1])


async def get_current_user(
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前登录用户."""
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(code=40102, message="Token 无效")
    return await get_user_by_id(db, user_id)


async def get_current_user_optional(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """可选鉴权：有 Token 且合法就返回 User；否则返回 None（不抛异常）.

    用于 `/analyses/sample` 这类"允许匿名体验，但若已登录也能拿到身份做埋点"的接口。
    与 `get_current_user` 不同，这里**任何解析失败都静默返回 None**，而非 401；
    调用方可以自行决定是否区分"已登录 / 未登录"行为。
    """
    if not authorization:
        return None
    try:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        payload = decode_access_token(parts[1])
        user_id = payload.get("sub")
        if not user_id:
            return None
        return await get_user_by_id(db, user_id)
    except Exception:
        # 匿名路径对任何异常都降级为"未登录"，不泄露细节
        return None
