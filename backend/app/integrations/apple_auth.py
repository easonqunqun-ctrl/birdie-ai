"""Sign in with Apple：校验 identity_token，换取稳定 `sub`.

Mock：`APPLE_MOCK_LOGIN=true` 且 token 以 `mock-` 开头时，基于哈希生成稳定 sub，便于联调。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import httpx
from jose import JWTError, jwt

from app.config import settings
from app.core.exceptions import UnauthorizedError

_APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
_APPLE_ISSUER = "https://appleid.apple.com"


@dataclass(frozen=True, slots=True)
class AppleIdentity:
    sub: str
    email: str | None = None


_jwks_cache: dict | None = None


async def _fetch_apple_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(_APPLE_JWKS_URL)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


def _mock_identity(token: str) -> AppleIdentity:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
    return AppleIdentity(sub=f"mock_apple_{digest}", email=None)


async def verify_apple_identity_token(identity_token: str) -> AppleIdentity:
    """校验 Apple identity_token，返回 `sub`（及可选 email）."""
    token = (identity_token or "").strip()
    if not token:
        raise UnauthorizedError(message="Apple 登录凭证无效", code=40104)

    if settings.APPLE_MOCK_LOGIN and token.startswith("mock-"):
        return _mock_identity(token)

    try:
        header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise UnauthorizedError(message="Apple 登录凭证无效", code=40104) from e

    kid = header.get("kid")
    if not kid:
        raise UnauthorizedError(message="Apple 登录凭证无效", code=40104)

    try:
        jwks = await _fetch_apple_jwks()
    except Exception as e:
        raise UnauthorizedError(
            message="无法校验 Apple 登录，请稍后重试", code=40104
        ) from e

    key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key is None:
        # 密钥轮换：清缓存再试一次
        global _jwks_cache
        _jwks_cache = None
        try:
            jwks = await _fetch_apple_jwks()
        except Exception as e:
            raise UnauthorizedError(
                message="无法校验 Apple 登录，请稍后重试", code=40104
            ) from e
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key is None:
        raise UnauthorizedError(message="Apple 登录凭证无效", code=40104)

    audiences = [
        a
        for a in [
            settings.APPLE_BUNDLE_ID,
            settings.APPLE_SERVICES_ID,
        ]
        if a
    ]
    if not audiences:
        raise UnauthorizedError(message="服务端未配置 Apple Bundle ID", code=40104)

    last_err: Exception | None = None
    for aud in audiences:
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=aud,
                issuer=_APPLE_ISSUER,
                options={"verify_at_hash": False},
            )
            break
        except JWTError as e:
            last_err = e
            payload = None
    else:
        raise UnauthorizedError(message="Apple 登录凭证无效", code=40104) from last_err
    if payload is None:
        raise UnauthorizedError(message="Apple 登录凭证无效", code=40104)

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise UnauthorizedError(message="Apple 登录凭证无效", code=40104)

    email = payload.get("email")
    return AppleIdentity(
        sub=sub.strip(),
        email=email.strip() if isinstance(email, str) and email.strip() else None,
    )
