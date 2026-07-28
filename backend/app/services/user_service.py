"""用户 service - 业务逻辑，路由层调它，不直接操作 ORM。

学习点：
- service 层 = 业务规则，路由层只负责「收请求、调 service、返响应」
- upsert = update or insert：登录场景天然要求「同一个 openid 只有一条记录」
- SQLModel 的 .add() 之后必须 .commit() + .refresh() 才能拿到自增 id
"""
from datetime import datetime

from sqlmodel import Session, select

from app.models.user import User


def upsert_by_openid(
    session: Session,
    *,
    openid: str,
    unionid: str | None = None,
    nickname: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """按 openid 查用户，不存在就建，存在就更新。

    Returns: 落库后的 User 对象（含 id）。
    """
    stmt = select(User).where(User.openid == openid)
    user = session.exec(stmt).first()

    if user is None:
        # 首次登录 - 创建
        user = User(
            openid=openid,
            unionid=unionid,
            nickname=nickname or "微信用户",
            avatar_url=avatar_url,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    # 二次登录 - 更新 unionid/nickname/avatar（前端传了的才覆盖）
    if unionid and user.unionid != unionid:
        user.unionid = unionid
    if nickname and user.nickname != nickname:
        user.nickname = nickname
    if avatar_url and user.avatar_url != avatar_url:
        user.avatar_url = avatar_url
    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
