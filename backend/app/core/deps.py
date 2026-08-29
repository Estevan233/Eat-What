"""依赖注入 - FastAPI 用 Depends() 注入。

学习点：
- get_db 是 generator，FastAPI 会自动 close session
- get_current_user 从 Authorization header 解析 JWT，查 User 表
- oauth2_scheme 自动从 header 拿 Bearer token
"""
from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from sqlmodel import Session

from app.core.config import get_settings
from app.core.errors import AuthError
from app.core.security import decode_token
from app.db import SessionLocal
from app.models.user import ACCOUNT_KINDS, ACCOUNT_STATUSES, User
from app.repositories.cloudbase_rdb import CloudBaseRdbClient
from app.repositories.cloudbase_repository import CloudBaseRepository, DatabaseSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/wx-login", auto_error=False)


@lru_cache
def get_cloudbase_repository() -> CloudBaseRepository:
    settings = get_settings()
    api_key = settings.cloudbase_server_api_key
    if api_key is None:
        raise RuntimeError('CLOUDBASE_APIKEY is required for cloudbase_rest')
    client = CloudBaseRdbClient(
        env_id=settings.cloudbase_env_id,
        api_key=api_key,
        timeout_seconds=settings.cloudbase_db_timeout_seconds,
        read_retries=settings.cloudbase_db_read_retries,
    )
    return CloudBaseRepository(client)


def get_db() -> Generator[Session | CloudBaseRepository, None, None]:
    """每个请求一个 Session。"""
    if get_settings().database_backend == 'cloudbase_rest':
        yield get_cloudbase_repository()
        return
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: DatabaseSession = Depends(get_db),
) -> User:
    """解析 JWT，查 User，失败抛 AuthError。

    路由用 Depends(get_current_user) 即可拿到当前 User 对象。
    """
    return resolve_token_user(session, token, require_active=True)


def optional_bearer_token(authorization: str | None) -> str | None:
    """Return a Bearer token when present, rejecting malformed credentials."""
    if authorization is None or not authorization.strip():
        return None
    scheme, token = get_authorization_scheme_param(authorization)
    if scheme.lower() != "bearer" or not token:
        raise AuthError("Authorization 格式无效")
    return token


def resolve_token_user(
    session: DatabaseSession,
    token: str | None,
    *,
    require_active: bool,
) -> User:
    """Resolve a signed business token to its current database identity."""
    if not token:
        raise AuthError("缺少 Authorization 头")

    payload = decode_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthError("token 里没有用户 id")

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise AuthError("token 里的 user id 不是数字") from None

    user = session.get(User, user_id)
    if user is None:
        raise AuthError(f"用户不存在: id={user_id}")
    if user.account_kind not in ACCOUNT_KINDS or user.account_status not in ACCOUNT_STATUSES:
        raise AuthError("账户状态无效")
    if require_active and (
        user.account_status != "active"
    ):
        raise AuthError("账户不可用")

    return user
