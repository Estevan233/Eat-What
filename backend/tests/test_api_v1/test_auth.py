"""T04 微信登录全链路测试。

覆盖 PRD 验收三条：
1. 首次登录 → 创建用户、返回 token
2. 二次登录 → 复用、更新 nickname/avatar
3. code 无效 → 401

学习点：
- monkeypatch 替换 wx_client 的方法，避免真调微信
- TestClient 模拟完整 HTTP 请求
- 验证 JWT 能解码出正确 user_id
"""
from unittest.mock import AsyncMock

import pytest

from app.core.security import decode_token
from app.models.user import User
from app.services.wx_client import Code2SessionResult


@pytest.fixture
def mock_wx_success(monkeypatch):
    """为兼容端点显式开闸，并构造成功的 code2session 返回。"""
    monkeypatch.setenv("ENABLE_CODE2SESSION", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def _mock(openid: str = "test_openid_001", unionid: str | None = None) -> None:
        from app.services import wx_client as mod
        result: Code2SessionResult = {
            "openid": openid,
            "session_key": "fake_session_key",
            "unionid": unionid,
        }
        mod.wx_client.code2session = AsyncMock(return_value=result)
    return _mock


def test_first_login_creates_user(client, session, mock_wx_success):
    """首次登录 → 创建用户、返回 token。"""
    mock_wx_success(openid="openid_new_user")

    res = client.post(
        "/api/v1/auth/wx-login",
        json={"code": "fake_code", "nickname": "张三", "avatar_url": "https://example.com/a.png"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True

    data = body["data"]
    assert "token" in data and len(data["token"]) > 0
    assert data["user"]["nickname"] == "张三"
    assert data["user"]["avatar_url"] == "https://example.com/a.png"

    # 验证 JWT 能解码出 user_id
    payload = decode_token(data["token"])
    user_id = int(payload["sub"])

    # 验证 User 表确实建了一条
    db_user = session.get(User, user_id)
    assert db_user is not None
    assert db_user.openid == "openid_new_user"
    assert db_user.nickname == "张三"


def test_second_login_reuses_and_updates(client, session, mock_wx_success):
    """同一个 openid 二次登录 → 复用同一行，更新 nickname/avatar。"""
    mock_wx_success(openid="openid_repeat")

    # 第一次登录
    res1 = client.post(
        "/api/v1/auth/wx-login",
        json={"code": "c1", "nickname": "李四", "avatar_url": "https://e.com/1.png"},
    )
    assert res1.status_code == 200
    user_id_1 = res1.json()["data"]["user"]["id"]

    # 第二次登录，换 nickname 和 avatar
    res2 = client.post(
        "/api/v1/auth/wx-login",
        json={"code": "c2", "nickname": "李四丰", "avatar_url": "https://e.com/2.png"},
    )
    assert res2.status_code == 200
    user_id_2 = res2.json()["data"]["user"]["id"]

    # 必须是同一个 user
    assert user_id_1 == user_id_2

    # 验证 nickname/avatar 被更新
    db_user = session.get(User, user_id_1)
    assert db_user is not None
    assert db_user.nickname == "李四丰"
    assert db_user.avatar_url == "https://e.com/2.png"

    # 验证表里只有一条记录
    from sqlmodel import select
    all_users = session.exec(select(User).where(User.openid == "openid_repeat")).all()
    assert len(all_users) == 1


def test_invalid_code_returns_401(client, mock_wx_success):
    """code 无效 → 微信返回 errcode → 抛 AuthError → HTTP 401。"""
    from app.core.errors import AuthError
    from app.services import wx_client as mod
    mod.wx_client.code2session = AsyncMock(side_effect=AuthError("微信登录失败: [40029] invalid code"))

    res = client.post("/api/v1/auth/wx-login", json={"code": "bad_code"})

    assert res.status_code == 401
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "AUTH_ERROR"


def test_get_current_user_with_valid_token(client, session, mock_wx_success):
    """登录后拿 token，再带 token 调一个需要登录的接口能成功。

    这里没建需要登录的接口，所以直接调 get_current_user 函数验证。
    """
    mock_wx_success(openid="openid_for_guard_test")
    res = client.post(
        "/api/v1/auth/wx-login",
        json={"code": "c"},
    )
    token = res.json()["data"]["token"]

    # 用 token 调 get_current_user（模拟路由里 Depends(get_current_user) 的行为）
    from app.core.deps import get_current_user
    from app.db import SessionLocal
    sess = SessionLocal()
    try:
        user = get_current_user(token=token, session=sess)
        assert user.openid == "openid_for_guard_test"
    finally:
        sess.close()
