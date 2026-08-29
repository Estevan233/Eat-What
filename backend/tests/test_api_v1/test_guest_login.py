"""游客登录端点测试 - POST /auth/guest-login。

覆盖：
1. 首次游客登录 → 创建 user，返回 token
2. 同一 guest_id 二次登录 → 复用同一 user 行
3. 不同 guest_id → 不同 user
4. guest_id 缺失 → 422（Pydantic 校验）
5. 游客 user 用 token 调需要登录的端点能成功（如 GET /profile）
6. 游客 user 在 user 表的 openid 带 `guest:` 前缀

学习点：
- 不需要 mock wx_client（游客登录不调微信）
- 验证 JWT 能解码出 user_id
"""
import uuid
from datetime import datetime

import pytest

from app.core.security import decode_token
from app.models.user import User
from app.services.user_service import GUEST_OPENID_PREFIX


def test_first_guest_login_creates_user(client, session):
    guest_id = str(uuid.uuid4())
    res = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": guest_id, "nickname": "体验员"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True

    data = body["data"]
    assert "token" in data and len(data["token"]) > 0
    assert data["user"]["nickname"] == "体验员"
    assert data["user"]["avatar_url"] is None
    assert data["user"]["account_kind"] == "guest"

    # JWT 能解出 user_id
    payload = decode_token(data["token"])
    user_id = int(payload["sub"])

    # DB 有一行，openid 带 guest: 前缀
    db_user = session.get(User, user_id)
    assert db_user is not None
    assert db_user.openid == f"{GUEST_OPENID_PREFIX}{guest_id}"
    assert db_user.nickname == "体验员"
    assert db_user.unionid is None
    assert db_user.account_kind == "guest"
    assert db_user.account_status == "active"
    assert db_user.merged_into_user_id is None
    assert db_user.merge_started_at is None
    assert db_user.merged_at is None


def test_same_guest_id_reuses_same_user(client, session):
    guest_id = str(uuid.uuid4())

    res1 = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": guest_id, "nickname": "游客一号"},
    )
    assert res1.status_code == 200
    user_id_1 = res1.json()["data"]["user"]["id"]

    # 二次登录，换 nickname
    res2 = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": guest_id, "nickname": "游客二号"},
    )
    assert res2.status_code == 200
    user_id_2 = res2.json()["data"]["user"]["id"]

    # 同一个 user
    assert user_id_1 == user_id_2

    # nickname 被更新
    db_user = session.get(User, user_id_1)
    assert db_user is not None
    assert db_user.nickname == "游客二号"

    # 表里只有一行
    from sqlmodel import select

    all_users = session.exec(
        select(User).where(User.openid == f"{GUEST_OPENID_PREFIX}{guest_id}")
    ).all()
    assert len(all_users) == 1


def test_different_guest_ids_create_different_users(client, session):
    res1 = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": str(uuid.uuid4())},
    )
    res2 = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": str(uuid.uuid4())},
    )
    assert res1.status_code == 200
    assert res2.status_code == 200

    user_id_1 = res1.json()["data"]["user"]["id"]
    user_id_2 = res2.json()["data"]["user"]["id"]
    assert user_id_1 != user_id_2


def test_guest_login_without_nickname_uses_default(client, session):
    """不传 nickname → 默认「游客」。"""
    res = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": str(uuid.uuid4())},
    )
    assert res.status_code == 200
    assert res.json()["data"]["user"]["nickname"] == "游客"


def test_guest_login_missing_guest_id_returns_422(client):
    """guest_id 缺失 → Pydantic 422。"""
    res = client.post("/api/v1/auth/guest-login", json={})
    assert res.status_code == 422


def test_guest_login_empty_guest_id_returns_422(client):
    """guest_id 为空串 → min_length=1 校验失败 422。"""
    res = client.post("/api/v1/auth/guest-login", json={"guest_id": ""})
    assert res.status_code == 422


def test_guest_token_works_for_protected_endpoint(client):
    """游客拿 token 调需要登录的 GET /profile 应该成功（profile=null 也算 200）。"""
    res_login = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": str(uuid.uuid4())},
    )
    token = res_login.json()["data"]["token"]

    res_profile = client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_profile.status_code == 200
    assert res_profile.json()["data"]["profile"] is None


@pytest.mark.parametrize("account_status", ["merging", "merged"])
def test_upgraded_guest_token_is_rejected_by_protected_endpoint(
    client,
    session,
    account_status: str,
) -> None:
    guest_id = f"old-token-{account_status}"
    login = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": guest_id},
    )
    token = login.json()["data"]["token"]
    guest_id_in_db = login.json()["data"]["user"]["id"]

    target = User(openid=f"wechat-old-token-target-{account_status}")
    session.add(target)
    session.commit()
    session.refresh(target)
    assert target.id is not None

    guest = session.get(User, guest_id_in_db)
    assert guest is not None
    guest.account_status = account_status
    guest.merged_into_user_id = target.id
    guest.merge_started_at = datetime.utcnow()
    guest.merged_at = datetime.utcnow() if account_status == "merged" else None
    session.add(guest)
    session.commit()

    response = client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_ERROR"
    assert guest_id not in response.text
    assert token not in response.text


def test_guest_login_does_not_call_wechat(client, monkeypatch):
    """游客登录不应触发任何微信 API 调用。

    把 wx_client.code2session 替换成「只要被调就 fail」的 mock。
    """
    def _unexpected_call(*_args, **_kwargs):
        raise AssertionError("游客登录不应调 wx_client.code2session")

    from app.services import wx_client as mod
    mod.wx_client.code2session = _unexpected_call  # type: ignore[assignment]

    res = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": str(uuid.uuid4())},
    )
    assert res.status_code == 200


@pytest.mark.parametrize("account_status", ["merging", "merged"])
def test_guest_login_rejects_upgraded_account(
    client,
    session,
    account_status: str,
) -> None:
    target = User(openid=f"wechat-target-{account_status}")
    session.add(target)
    session.commit()
    session.refresh(target)
    assert target.id is not None

    guest_id = f"upgraded-{account_status}"
    guest = User(
        openid=f"{GUEST_OPENID_PREFIX}{guest_id}",
        account_kind="guest",
        account_status=account_status,
        merged_into_user_id=target.id,
        merge_started_at=datetime.utcnow(),
        merged_at=datetime.utcnow() if account_status == "merged" else None,
        nickname="墓碑账户",
    )
    session.add(guest)
    session.commit()

    response = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": guest_id, "nickname": "不应更新"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "GUEST_ACCOUNT_UPGRADED"
    session.refresh(guest)
    assert guest.nickname == "墓碑账户"
