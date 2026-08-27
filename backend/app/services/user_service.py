"""用户 service - 业务逻辑，路由层调它，不直接操作 ORM。

登录以 openid 为唯一身份：首次创建，后续只更新前端明确提供的资料。
SQLAlchemy 与 CloudBase REST 使用各自明确的写入语义。
"""

from datetime import datetime

from sqlmodel import select

from app.models.user import User
from app.repositories.cloudbase_rdb import RdbFilter
from app.repositories.cloudbase_repository import (
    CloudBaseRepository,
    DatabaseSession,
    is_cloudbase_repository,
)


def _upsert_by_openid_cloudbase(
    session: CloudBaseRepository,
    *,
    openid: str,
    unionid: str | None,
    nickname: str | None,
    avatar_url: str | None,
) -> User:
    user = session.first(
        User,
        filters=(RdbFilter("openid", "eq", openid),),
    )
    if user is None:
        return session.insert(
            User(
                openid=openid,
                unionid=unionid,
                nickname=nickname or "微信用户",
                avatar_url=avatar_url,
            )
        )

    if unionid:
        user.unionid = unionid
    if nickname:
        user.nickname = nickname
    if avatar_url:
        user.avatar_url = avatar_url
    user.updated_at = datetime.utcnow()
    if user.id is None:
        raise RuntimeError("REST 查询返回的 user.id 不应为 None")
    return session.update(
        user,
        filters=(RdbFilter("id", "eq", user.id),),
    )


def upsert_by_openid(
    session: DatabaseSession,
    *,
    openid: str,
    unionid: str | None = None,
    nickname: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """按 openid 查用户，不存在就建，存在就更新。"""
    if is_cloudbase_repository(session):
        return _upsert_by_openid_cloudbase(
            session,
            openid=openid,
            unionid=unionid,
            nickname=nickname,
            avatar_url=avatar_url,
        )

    stmt = select(User).where(User.openid == openid)
    user = session.exec(stmt).first()

    if user is None:
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


def update_public_profile(
    session: DatabaseSession,
    user: User,
    *,
    nickname: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """仅按已认证用户 id 更新公开资料，兼容 SQLAlchemy 与 HTTP Repository。"""
    if user.id is None:
        raise RuntimeError("已认证用户的 user.id 不应为 None")

    if nickname is not None:
        user.nickname = nickname
    if avatar_url is not None:
        user.avatar_url = avatar_url
    user.updated_at = datetime.utcnow()

    if is_cloudbase_repository(session):
        return session.update(
            user,
            filters=(RdbFilter("id", "eq", user.id),),
        )

    session.add(user)
    session.commit()
    session.refresh(user)
    return user


GUEST_OPENID_PREFIX = "guest:"
GUEST_DEFAULT_NICKNAME = "游客"


def get_or_create_guest(
    session: DatabaseSession,
    *,
    guest_id: str,
    nickname: str | None = None,
) -> User:
    """按稳定的游客标识复用或创建用户。"""
    openid = f"{GUEST_OPENID_PREFIX}{guest_id}"
    return upsert_by_openid(
        session,
        openid=openid,
        unionid=None,
        nickname=nickname or GUEST_DEFAULT_NICKNAME,
        avatar_url=None,
    )
