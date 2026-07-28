"""安全工具 - JWT 签发/校验 + 密码哈希。

学习点：
- JWT payload 含 sub(用户 id)、iat(签发)、exp(过期)
- passlib[bcrypt] 适合多账号体系；微信登录虽无密码，但保留接口
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.errors import AuthError

_settings = get_settings()
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(user_id: int) -> str:
    """签发 JWT，TTL 由 settings.jwt_ttl_minutes 控制。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_settings.jwt_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """校验并解码 JWT。失败抛 AuthError。"""
    try:
        return jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise AuthError("登录已过期，请重新登录") from None
    except jwt.InvalidTokenError:
        raise AuthError("无效的登录凭证") from None


def hash_password(raw: str) -> str:
    # bcrypt 72 字节上限：截断避免 ValueError（passlib 不自动截断）
    raw_bytes = raw.encode("utf-8")[:72]
    return _pwd_context.hash(raw_bytes)


def verify_password(raw: str, hashed: str) -> bool:
    raw_bytes = raw.encode("utf-8")[:72]
    return _pwd_context.verify(raw_bytes, hashed)
