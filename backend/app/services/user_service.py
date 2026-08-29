"""用户 service - 业务逻辑，路由层调它，不直接操作 ORM。

登录以 openid 为唯一身份：首次创建，后续只更新前端明确提供的资料。
SQLAlchemy 与 CloudBase REST 使用各自明确的写入语义。
"""

from datetime import datetime
from typing import NoReturn

from sqlalchemy import update
from sqlmodel import Session, col, select

from app.core.errors import AccountStateConflictError, GuestAccountUpgradedError
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
                account_kind="wechat",
                account_status="active",
                nickname=nickname or "微信用户",
                avatar_url=avatar_url,
            )
        )

    if user.account_kind != "wechat" or user.account_status != "active":
        raise AccountStateConflictError
    values: dict[str, object] = {"updated_at": datetime.utcnow()}
    if unionid:
        values["unionid"] = unionid
    if nickname:
        values["nickname"] = nickname
    if avatar_url:
        values["avatar_url"] = avatar_url
    if user.id is None:
        raise RuntimeError("REST 查询返回的 user.id 不应为 None")
    updated = session.update_fields(
        User,
        values=values,
        filters=(
            RdbFilter("id", "eq", user.id),
            RdbFilter("account_kind", "eq", "wechat"),
            RdbFilter("account_status", "eq", "active"),
        ),
    )
    if updated is None:
        raise AccountStateConflictError
    return updated


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
            account_kind="wechat",
            account_status="active",
            nickname=nickname or "微信用户",
            avatar_url=avatar_url,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    if user.account_kind != "wechat" or user.account_status != "active":
        raise AccountStateConflictError
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


def _public_profile_values(
    *,
    nickname: str | None = None,
    avatar_url: str | None = None,
) -> dict[str, object]:
    values: dict[str, object] = {"updated_at": datetime.utcnow()}
    if nickname is not None:
        values["nickname"] = nickname
    if avatar_url is not None:
        values["avatar_url"] = avatar_url
    return values


def _update_public_profile_cloudbase(
    session: CloudBaseRepository,
    *,
    user_id: int,
    account_kind: str,
    values: dict[str, object],
) -> User:
    updated = session.update_fields(
        User,
        values=values,
        filters=(
            RdbFilter("id", "eq", user_id),
            RdbFilter("account_kind", "eq", account_kind),
            RdbFilter("account_status", "eq", "active"),
        ),
    )
    if updated is None:
        raise AccountStateConflictError
    return updated


def _update_public_profile_sqlalchemy(
    session: Session,
    *,
    user_id: int,
    account_kind: str,
    values: dict[str, object],
) -> User:
    result = session.connection().execute(
        update(User)
        .where(
            col(User.id) == user_id,
            col(User.account_kind) == account_kind,
            col(User.account_status) == "active",
        )
        .values(**values)
    )
    if result.rowcount != 1:
        session.rollback()
        raise AccountStateConflictError

    session.commit()
    statement = (
        select(User)
        .where(col(User.id) == user_id)
        .execution_options(populate_existing=True)
    )
    current = session.exec(statement).first()
    if (
        current is None
        or current.account_kind != account_kind
        or current.account_status != "active"
    ):
        raise AccountStateConflictError
    return current


def update_public_profile(
    session: DatabaseSession,
    user: User,
    *,
    nickname: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """仅按已认证用户 id 更新公开资料，兼容 SQLAlchemy 与 HTTP Repository。"""
    user_id = user.id
    if user_id is None:
        raise RuntimeError("已认证用户的 user.id 不应为 None")
    account_kind = user.account_kind
    if account_kind not in {"guest", "wechat"}:
        raise AccountStateConflictError

    values = _public_profile_values(
        nickname=nickname,
        avatar_url=avatar_url,
    )
    if is_cloudbase_repository(session):
        return _update_public_profile_cloudbase(
            session,
            user_id=user_id,
            account_kind=account_kind,
            values=values,
        )

    return _update_public_profile_sqlalchemy(
        session,
        user_id=user_id,
        account_kind=account_kind,
        values=values,
    )


GUEST_OPENID_PREFIX = "guest:"
GUEST_DEFAULT_NICKNAME = "游客"


def _ensure_active_guest(user: User) -> None:
    if user.account_kind != "guest" or user.account_status != "active":
        raise GuestAccountUpgradedError


def _raise_guest_write_conflict(current: User | None) -> NoReturn:
    """Map a failed conditional write after rereading the current account state."""
    if current is not None:
        _ensure_active_guest(current)
    raise AccountStateConflictError


def _read_cloudbase_guest(session: CloudBaseRepository, *, openid: str) -> User | None:
    return session.first(
        User,
        filters=(RdbFilter("openid", "eq", openid),),
    )


def _update_active_cloudbase_guest(
    session: CloudBaseRepository,
    *,
    user_id: int,
    nickname: str,
) -> User | None:
    return session.update_fields(
        User,
        values={
            "nickname": nickname,
            "updated_at": datetime.utcnow(),
        },
        filters=(
            RdbFilter("id", "eq", user_id),
            RdbFilter("account_kind", "eq", "guest"),
            RdbFilter("account_status", "eq", "active"),
        ),
    )


def _get_or_create_cloudbase_guest(
    session: CloudBaseRepository,
    *,
    openid: str,
    nickname: str,
) -> User:
    user = _read_cloudbase_guest(session, openid=openid)
    if user is None:
        return session.insert(
            User(
                openid=openid,
                account_kind="guest",
                account_status="active",
                nickname=nickname,
            )
        )

    _ensure_active_guest(user)
    user_id = user.id
    if user_id is None:
        raise RuntimeError("REST 查询返回的 user.id 不应为 None")
    updated = _update_active_cloudbase_guest(
        session,
        user_id=user_id,
        nickname=nickname,
    )
    if updated is not None:
        return updated

    current = _read_cloudbase_guest(session, openid=openid)
    _raise_guest_write_conflict(current)


def _read_sqlalchemy_guest(
    session: Session,
    *,
    openid: str,
    refresh_existing: bool = False,
) -> User | None:
    statement = select(User).where(User.openid == openid)
    if refresh_existing:
        statement = statement.execution_options(populate_existing=True)
    return session.exec(statement).first()


def _update_active_sqlalchemy_guest(
    session: Session,
    *,
    user_id: int,
    nickname: str,
) -> bool:
    result = session.connection().execute(
        update(User)
        .where(
            col(User.id) == user_id,
            col(User.account_kind) == "guest",
            col(User.account_status) == "active",
        )
        .values(
            nickname=nickname,
            updated_at=datetime.utcnow(),
        )
    )
    return result.rowcount == 1


def _get_or_create_sqlalchemy_guest(
    session: Session,
    *,
    openid: str,
    nickname: str,
) -> User:
    user = _read_sqlalchemy_guest(session, openid=openid)
    if user is None:
        user = User(
            openid=openid,
            account_kind="guest",
            account_status="active",
            nickname=nickname,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    _ensure_active_guest(user)
    user_id = user.id
    if user_id is None:
        raise RuntimeError("游客 user.id 不应为 None")
    if not _update_active_sqlalchemy_guest(
        session,
        user_id=user_id,
        nickname=nickname,
    ):
        session.rollback()
        current = _read_sqlalchemy_guest(session, openid=openid)
        _raise_guest_write_conflict(current)

    session.commit()
    current = _read_sqlalchemy_guest(
        session,
        openid=openid,
        refresh_existing=True,
    )
    if current is None:
        raise AccountStateConflictError
    _ensure_active_guest(current)
    return current


def get_or_create_guest(
    session: DatabaseSession,
    *,
    guest_id: str,
    nickname: str | None = None,
) -> User:
    """按稳定的游客标识复用或创建用户。"""
    openid = f"{GUEST_OPENID_PREFIX}{guest_id}"
    guest_nickname = nickname or GUEST_DEFAULT_NICKNAME

    if is_cloudbase_repository(session):
        return _get_or_create_cloudbase_guest(
            session,
            openid=openid,
            nickname=guest_nickname,
        )
    return _get_or_create_sqlalchemy_guest(
        session,
        openid=openid,
        nickname=guest_nickname,
    )
