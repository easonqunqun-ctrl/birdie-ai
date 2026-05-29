"""安全相关：JWT 签发与校验、ID 生成器."""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from nanoid import generate

from app.config import settings
from app.core.exceptions import UnauthorizedError

# nanoid 字母表（去掉容易混淆的字符）
ID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
ID_LENGTH = 16


def new_id(prefix: str) -> str:
    """生成带前缀的业务 ID，例如 usr_a1b2c3..."""
    return f"{prefix}_{generate(alphabet=ID_ALPHABET, size=ID_LENGTH)}"


def new_invite_code() -> str:
    """生成 6 位邀请码（大写字母+数字，去除易混淆字符）."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉 I/O/0/1
    return generate(alphabet=alphabet, size=6)


def create_access_token(
    user_id: str,
    openid: str,
    membership: str = "free",
    extra: dict[str, Any] | None = None,
    *,
    role: str = "user",
) -> tuple[str, int]:
    """签发 JWT。返回 (token, expires_in_seconds)."""

    expires_delta = timedelta(days=settings.JWT_ACCESS_TOKEN_EXPIRE_DAYS)
    now = datetime.now(UTC)
    expire_at = now + expires_delta

    payload: dict[str, Any] = {
        "sub": user_id,
        "openid": openid,
        "membership": membership,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire_at.timestamp()),
    }
    if extra:
        payload.update(extra)

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def token_role(payload: dict[str, Any]) -> str:
    """JWT 内角色；缺省 user（兼容旧 token）."""

    role = payload.get("role")
    return role if role in {"user", "coach"} else "user"


def decode_access_token(token: str) -> dict[str, Any]:
    """解析并校验 JWT。失败抛 UnauthorizedError."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as e:
        raise UnauthorizedError(code=40102, message="Token 无效", detail=str(e)) from e

    if not payload.get("sub"):
        raise UnauthorizedError(code=40102, message="Token 无效")
    return payload
