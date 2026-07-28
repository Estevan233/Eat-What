"""T05 用户档案 API 测试。

覆盖 PRD 验收 6 条：
1. 未登录 GET → 401
2. 登录后无档案 → profile=null
3. PUT 创建
4. PUT 二次更新 height
5. height 越界 → 422
6. gender 非法 → 422
7. forbidden_tag 非法 → 422

学习点：
- 通过 wx-login mock 端点拿 token，再带 Authorization 头调 profile 端点
- 422 是 Pydantic 校验失败时的默认状态码（FastAPI 的 RequestValidationError）
"""
from unittest.mock import AsyncMock

import pytest

from app.services.wx_client import Code2SessionResult


@pytest.fixture
def auth_token(client, monkeypatch):
    """构造一个登录成功场景，返回带 token 的 Authorization header。"""
    # mock wx_client 返回成功
    from app.services import wx_client as mod
    result: Code2SessionResult = {
        "openid": "openid_for_profile_test",
        "session_key": "fake_session_key",
        "unionid": None,
    }
    mod.wx_client.code2session = AsyncMock(return_value=result)

    res = client.post(
        "/api/v1/auth/wx-login",
        json={"code": "fake_code"},
    )
    assert res.status_code == 200
    token = res.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


VALID_BODY = {
    "birthday": "1990-01-15",
    "gender": "male",
    "height_cm": 175,
    "weight_kg": 70.0,
    "forbidden_tags": ["pork", "spicy"],
}


# --- 验收 1: 未登录 401 ---


def test_get_profile_unauthenticated_returns_401(client):
    res = client.get("/api/v1/profile")
    assert res.status_code == 401
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "AUTH_ERROR"


# --- 验收 2: 登录后无档案 → null ---


def test_get_profile_returns_null_when_no_profile(client, auth_token):
    res = client.get("/api/v1/profile", headers=auth_token)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["profile"] is None
    assert "id" in data
    assert "nickname" in data


# --- 验收 3: PUT 创建 ---


def test_put_profile_creates(client, auth_token, session):
    res = client.put("/api/v1/profile", json=VALID_BODY, headers=auth_token)
    assert res.status_code == 200
    profile = res.json()["data"]
    assert profile["birthday"] == "1990-01-15"
    assert profile["gender"] == "male"
    assert profile["height_cm"] == 175
    assert profile["weight_kg"] == 70.0
    assert profile["forbidden_tags"] == ["pork", "spicy"]
    assert profile["zodiac_sign"] is None  # T08 占位

    # 再 GET 验证落库
    res2 = client.get("/api/v1/profile", headers=auth_token)
    data = res2.json()["data"]
    assert data["profile"] is not None
    assert data["profile"]["birthday"] == "1990-01-15"


# --- 验收 4: PUT 二次更新 height ---


def test_put_profile_updates_height(client, auth_token):
    # 第一次创建
    res1 = client.put("/api/v1/profile", json=VALID_BODY, headers=auth_token)
    assert res1.status_code == 200
    assert res1.json()["data"]["height_cm"] == 175

    # 第二次更新身高
    body2 = {**VALID_BODY, "height_cm": 180}
    res2 = client.put("/api/v1/profile", json=body2, headers=auth_token)
    assert res2.status_code == 200
    assert res2.json()["data"]["height_cm"] == 180

    # 再 GET 是新值
    res3 = client.get("/api/v1/profile", headers=auth_token)
    assert res3.json()["data"]["profile"]["height_cm"] == 180


# --- 验收 5: height 越界 422 ---


def test_put_profile_invalid_height_returns_422(client, auth_token):
    body = {**VALID_BODY, "height_cm": 300}
    res = client.put("/api/v1/profile", json=body, headers=auth_token)
    assert res.status_code == 422


# --- 验收 6: gender 非法 422 ---


def test_put_profile_invalid_gender_returns_422(client, auth_token):
    body = {**VALID_BODY, "gender": "unknown"}
    res = client.put("/api/v1/profile", json=body, headers=auth_token)
    assert res.status_code == 422


# --- 验收 7: forbidden_tag 非法 → 422（service 层 ValidationError） ---


def test_put_profile_invalid_forbidden_tag_returns_422(client, auth_token):
    body = {**VALID_BODY, "forbidden_tags": ["pork", "unknown_tag"]}
    res = client.put("/api/v1/profile", json=body, headers=auth_token)
    # service 抛 ValidationError → 422
    assert res.status_code == 422
    body_json = res.json()
    # ValidationError 的 message 含未知标签
    assert "未知" in body_json["message"] or "unknown_tag" in body_json["message"]
