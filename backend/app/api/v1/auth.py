"""认证相关接口：微信登录、Token 刷新."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_token_payload
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import CoachRoleSwitchError, NotFoundError
from app.core.security import create_access_token, token_role
from app.integrations.apple_auth import verify_apple_identity_token
from app.integrations.wechat import code2session, oauth2_access_token_app
from app.models.user import User
from app.schemas.auth import RoleSwitchRequest, RoleSwitchResponse
from app.schemas.base import APIResponse, ok
from app.schemas.user import (
    AppleLoginRequest,
    TokenRefreshResponse,
    WechatLoginRequest,
    WechatLoginResponse,
)
from app.services import coach_profile_service as coach_prof_svc
from app.services import user_service
from app.services.user_presenter import build_user_response

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
        openid=user.wechat_subject_for_jwt(),
        membership=user.membership_type,
        role="user",
    )

    return ok(
        WechatLoginResponse(
            token=token,
            expires_in=expires_in,
            is_new_user=is_new_user,
            user=build_user_response(user),
        )
    )


@router.post(
    "/wechat-open-login",
    summary="微信开放平台移动应用登录（RN App OAuth2）",
    response_model=APIResponse[WechatLoginResponse],
)
async def wechat_open_login(
    payload: WechatLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用 App 拉起微信授权返回的 `code`（非小程序 `wx.login` code）换取 JWT。

    **须在微信开放平台绑定移动应用**；与小程序共用同一开放平台主体时，`unionid` 可用于合并帐号。
    """
    oauth = await oauth2_access_token_app(payload.code)
    user, is_new_user = await user_service.login_or_create_user_app_oauth(
        db,
        oauth,
        invite_code=payload.invite_code,
    )
    await db.commit()

    token, expires_in = create_access_token(
        user_id=user.id,
        openid=user.wechat_subject_for_jwt(),
        membership=user.membership_type,
        role="user",
    )

    return ok(
        WechatLoginResponse(
            token=token,
            expires_in=expires_in,
            is_new_user=is_new_user,
            user=build_user_response(user),
        )
    )


@router.post(
    "/apple-login",
    summary="Sign in with Apple（Flutter App）",
    response_model=APIResponse[WechatLoginResponse],
)
async def apple_login(
    payload: AppleLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """校验 Apple `identity_token` 后签发与微信登录同形 JWT.

    本地 / 测试：`APPLE_MOCK_LOGIN=true` 时可用 `mock-…` 前缀 token 联调。
    """
    identity = await verify_apple_identity_token(payload.identity_token)
    user, is_new_user = await user_service.login_or_create_user_apple(
        db,
        identity,
        invite_code=payload.invite_code,
        full_name=payload.full_name,
    )
    await db.commit()

    token, expires_in = create_access_token(
        user_id=user.id,
        openid=user.wechat_subject_for_jwt(),
        membership=user.membership_type,
        role="user",
    )

    return ok(
        WechatLoginResponse(
            token=token,
            expires_in=expires_in,
            is_new_user=is_new_user,
            user=build_user_response(user),
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
        openid=user.wechat_subject_for_jwt(),
        membership=user.membership_type,
        role=token_role(payload),
    )
    return ok(TokenRefreshResponse(token=token, expires_in=expires_in))


@router.post(
    "/role-switch",
    summary="切换 user/coach 身份（M8-02）",
    response_model=APIResponse[RoleSwitchResponse],
)
async def role_switch(
    body: RoleSwitchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.PHASE2_COACH_ENABLED:
        raise NotFoundError(code=40406, message="教练功能未开放")
    if body.role == "coach":
        try:
            await coach_prof_svc.assert_active_coach(db, user=user)
        except Exception as exc:
            from app.core.exceptions import CoachNotVerifiedError

            if isinstance(exc, CoachNotVerifiedError):
                raise CoachRoleSwitchError() from exc
            raise
    token, expires_in = create_access_token(
        user_id=user.id,
        openid=user.wechat_subject_for_jwt(),
        membership=user.membership_type,
        role=body.role,
    )
    return ok(RoleSwitchResponse(token=token, expires_in=expires_in, role=body.role))
