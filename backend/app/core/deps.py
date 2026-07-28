"""依赖注入 - FastAPI 用 Depends() 注入。

学习点：
- get_db 是 generator，FastAPI 会自动 close session
- get_current_user 从 Authorization header 解析 JWT，查 User 表
- oauth2_scheme 自动从 header 拿 Bearer token
"""
from collections.abc import Generator

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from app.core.errors import AuthError
from app.core.security import decode_token
from app.db import SessionLocal
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/wx-login", auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """每个请求一个 Session。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: Session = Depends(get_db),
) -> User:
    """解析 JWT，查 User，失败抛 AuthError。

    路由用 Depends(get_current_user) 即可拿到当前 User 对象。
    """
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

    stmt = select(User).where(User.id == user_id)
    user = session.exec(stmt).first()
    if user is None:
        raise AuthError(f"用户不存在: id={user_id}")

    return user
