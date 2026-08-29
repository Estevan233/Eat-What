"""账户状态读取与迟到写入之间的确定性时序回归。"""

from datetime import datetime

import pytest
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from app.core.errors import AccountStateConflictError, GuestAccountUpgradedError
from app.models.user import User
from app.services.user_service import get_or_create_guest, update_public_profile


class _FirstResult:
    def __init__(self, user: User) -> None:
        self.user = user

    def first(self) -> User:
        return self.user


def test_sqlalchemy_guest_late_relogin_cannot_update_merged_tombstone(
    tmp_path,
    monkeypatch,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'guest-race.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as setup:
        target = User(openid="sql-race-target")
        setup.add(target)
        setup.commit()
        setup.refresh(target)
        assert target.id is not None
        guest = User(
            openid="guest:sql-race",
            account_kind="guest",
            nickname="合并前游客",
        )
        setup.add(guest)
        setup.commit()
        setup.refresh(guest)
        assert guest.id is not None
        guest_id = guest.id
        target_id = target.id

    with Session(engine) as session:
        original_exec = session.exec
        race_injected = False

        def exec_with_race(statement, *args, **kwargs):
            nonlocal race_injected
            if not race_injected and getattr(statement, "is_select", False):
                result = original_exec(statement, *args, **kwargs)
                stale_guest = result.first()
                assert stale_guest is not None
                session.expunge(stale_guest)
                session.rollback()
                with Session(engine) as concurrent:
                    concurrent.exec(
                        update(User)
                        .where(User.id == guest_id)
                        .values(
                            account_status="merged",
                            merged_into_user_id=target_id,
                            merge_started_at=datetime.utcnow(),
                            merged_at=datetime.utcnow(),
                        )
                    )
                    concurrent.commit()
                race_injected = True
                return _FirstResult(stale_guest)
            return original_exec(statement, *args, **kwargs)

        monkeypatch.setattr(session, "exec", exec_with_race)

        with pytest.raises(GuestAccountUpgradedError) as raised:
            get_or_create_guest(
                session,
                guest_id="sql-race",
                nickname="迟到游客",
            )

    assert raised.value.code == "GUEST_ACCOUNT_UPGRADED"
    with Session(engine) as verify:
        stored_guest = verify.get(User, guest_id)
        assert stored_guest is not None
        assert stored_guest.account_status == "merged"
        assert stored_guest.merged_into_user_id == target_id
        assert stored_guest.nickname == "合并前游客"


def test_sqlalchemy_guest_relogin_returns_latest_nickname_with_unexpired_session(
    tmp_path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'guest-refresh.db'}")
    SQLModel.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    with session_factory() as session:
        created = get_or_create_guest(
            session,
            guest_id="sql-refresh",
            nickname="游客一号",
        )
        updated = get_or_create_guest(
            session,
            guest_id="sql-refresh",
            nickname="游客二号",
        )

        assert created.id == updated.id
        assert updated.nickname == "游客二号"


def test_sqlalchemy_guest_merge_after_update_commit_is_seen_by_final_recheck(
    tmp_path,
    monkeypatch,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'guest-post-commit-race.db'}")
    SQLModel.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    with session_factory() as setup:
        target = User(
            openid="sql-post-commit-target",
            account_kind="wechat",
            account_status="active",
        )
        guest = User(
            openid="guest:sql-post-commit-race",
            account_kind="guest",
            account_status="active",
            nickname="合并前游客",
        )
        setup.add(target)
        setup.add(guest)
        setup.commit()
        assert target.id is not None
        assert guest.id is not None
        target_id = target.id
        guest_id = guest.id

    with session_factory() as session:
        original_exec = session.exec
        select_calls = 0
        race_injected = False

        def exec_with_post_commit_race(statement, *args, **kwargs):
            nonlocal race_injected, select_calls
            if getattr(statement, "is_select", False):
                select_calls += 1
                if select_calls == 2:
                    with session_factory() as concurrent:
                        concurrent.exec(
                            update(User)
                            .where(User.id == guest_id)
                            .values(
                                account_status="merged",
                                merged_into_user_id=target_id,
                                merge_started_at=datetime.utcnow(),
                                merged_at=datetime.utcnow(),
                            )
                        )
                        concurrent.commit()
                    race_injected = True
            return original_exec(statement, *args, **kwargs)

        monkeypatch.setattr(session, "exec", exec_with_post_commit_race)

        with pytest.raises(GuestAccountUpgradedError) as raised:
            get_or_create_guest(
                session,
                guest_id="sql-post-commit-race",
                nickname="迟到游客",
            )

    assert race_injected is True
    assert raised.value.code == "GUEST_ACCOUNT_UPGRADED"
    with session_factory() as verify:
        stored_guest = verify.get(User, guest_id)
        assert stored_guest is not None
        assert stored_guest.account_status == "merged"
        assert stored_guest.merged_into_user_id == target_id
        assert stored_guest.nickname == "迟到游客"


@pytest.mark.parametrize("account_status", ["merging", "merged"])
def test_sqlalchemy_public_profile_late_update_cannot_modify_merge_tombstone(
    tmp_path,
    account_status: str,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / f'profile-{account_status}-race.db'}")
    SQLModel.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    with session_factory() as setup:
        target = User(
            openid=f"profile-{account_status}-target",
            account_kind="wechat",
            account_status="active",
        )
        guest = User(
            openid=f"guest:profile-{account_status}-race",
            account_kind="guest",
            account_status="active",
            nickname="合并前昵称",
            avatar_url="cloud://avatar/before.png",
        )
        setup.add(target)
        setup.add(guest)
        setup.commit()
        assert target.id is not None
        assert guest.id is not None
        target_id = target.id
        guest_id = guest.id

    with session_factory() as session:
        stale_guest = session.get(User, guest_id)
        assert stale_guest is not None
        assert stale_guest.account_status == "active"
        session.commit()

        with session_factory() as concurrent:
            concurrent.exec(
                update(User)
                .where(User.id == guest_id)
                .values(
                    account_status=account_status,
                    merged_into_user_id=target_id,
                    merge_started_at=datetime.utcnow(),
                    merged_at=(
                        datetime.utcnow() if account_status == "merged" else None
                    ),
                )
            )
            concurrent.commit()

        with pytest.raises(AccountStateConflictError) as raised:
            update_public_profile(
                session,
                stale_guest,
                nickname="迟到昵称",
                avatar_url="cloud://avatar/late.png",
            )

    assert raised.value.code == "ACCOUNT_STATE_CONFLICT"
    with session_factory() as verify:
        stored_guest = verify.get(User, guest_id)
        assert stored_guest is not None
        assert stored_guest.account_status == account_status
        assert stored_guest.merged_into_user_id == target_id
        assert stored_guest.nickname == "合并前昵称"
        assert stored_guest.avatar_url == "cloud://avatar/before.png"


def test_sqlalchemy_public_profile_update_returns_latest_fields(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'profile-update.db'}")
    SQLModel.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    with session_factory() as setup:
        guest = User(
            openid="guest:profile-update",
            account_kind="guest",
            account_status="active",
            nickname="更新前昵称",
            avatar_url="cloud://avatar/before.png",
        )
        setup.add(guest)
        setup.commit()
        assert guest.id is not None
        guest_id = guest.id

    with session_factory() as session:
        guest = session.get(User, guest_id)
        assert guest is not None

        updated = update_public_profile(
            session,
            guest,
            nickname="更新后昵称",
            avatar_url="cloud://avatar/after.png",
        )

        assert updated.nickname == "更新后昵称"
        assert updated.avatar_url == "cloud://avatar/after.png"
        assert updated.account_status == "active"
