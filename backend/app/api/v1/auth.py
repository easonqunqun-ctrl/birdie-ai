"""认证相关接口：微信登录、Token 刷新."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_token_payload
from app.core.database import get_db
from app.core.security import create_access_token
from app.integrations.wechat import code2session
from app.schemas.base import APIResponse, ok
from app.schemas.user import (
    TokenRefreshResponse,
    UserResponse,
    WechatLoginRequest,
    WechatLoginResponse,
)
from app.services import payment_service, user_service


def _user_response(user: object) -> UserResponse:
    """构造含会员派生字段的 UserResponse（auth 路径复用）."""
    data = UserResponse.model_validate(user).model_dump()
    data["is_member"] = payment_service.is_member(user)
    data["membership_days_remaining"] = payment_service.days_remaining(user)
    return UserResponse(**data)

router = APIRouter()


@router.post(
    "/wechat-login",
    summary="微信小程序登录",
    response_model=APIResponse[WechatLoginResponse],
)
async def wechat_login(
    payload: WechatLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用 wx.login 拿到的 code 换取 JWT Token.

    本地开发模式下（WECHAT_MOCK_LOGIN=true），任意 code 都会基于其哈希
    生成一个稳定的 mock openid，便于联调。
    """
    wechat = await code2session(payload.code)
    user, is_new_user = await user_service.login_or_create_user(
        db,
        wechat,
        invite_code=payload.invite_code,
    )
    await db.commit()

    token, expires_in = create_access_token(
        user_id=user.id,
        openid=user.wechat_openid,
        membership=user.membership_type,
    )

    return ok(
        WechatLoginResponse(
            token=token,
            expires_in=expires_in,
            is_new_user=is_new_user,
            user=_user_response(user),
        )
    )


@router.post(
    "/refresh-token",
    summary="刷新 Token",
    response_model=APIResponse[TokenRefreshResponse],
)
async def refresh_token(
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """用未过期的 Token 换取新 Token（延长有效期）."""
    user_id = payload["sub"]
    user = await user_service.get_user_by_id(db, user_id)
    token, expires_in = create_access_token(
        user_id=user.id,
        openid=user.wechat_openid,
        membership=user.membership_type,
    )
    return ok(TokenRefreshResponse(token=token, expires_in=expires_in))
