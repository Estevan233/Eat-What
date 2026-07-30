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


# 游客 openid 前缀 - 与真实微信 openid 命名空间隔离，便于将来审计 / 迁移
GUEST_OPENID_PREFIX = "guest:"

# 游客 nickname 默认前缀（前端可在登录页让用户输入，未输入时用此默认）
GUEST_DEFAULT_NICKNAME = "游客"


def get_or_create_guest(
    session: Session,
    *,
    guest_id: str,
    nickname: str | None = None,
) -> User:
    """游客登录：按 guest_id 复用 / 创建一个伪 openid 用户。

    设计：
    - openid 命名空间用 `guest:<guest_id>` 与真实微信 openid 隔离
    - guest_id 由前端生成并落 storage，下次登录传回同一 guest_id → 复用同一行
    - nickname 不传时默认「游客」
    - 不支持 unionid（游客无微信身份）

    Args:
        session: SQLModel Session
        guest_id: 前端生成的游客标识（建议 UUID v4），同一 guest_id 总是同一 user
        nickname: 可选昵称，未传用默认

    Returns:
        落库后的 User 对象（含 id）。
    """
    openid = f"{GUEST_OPENID_PREFIX}{guest_id}"
    return upsert_by_openid(
        session,
        openid=openid,
        unionid=None,
        nickname=nickname or GUEST_DEFAULT_NICKNAME,
        avatar_url=None,
    )
