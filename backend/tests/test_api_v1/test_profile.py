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
- 通过 guest-login 拿 token，再带 Authorization 头调 profile 端点
- 422 是 Pydantic 校验失败时的默认状态码（FastAPI 的 RequestValidationError）
"""

import pytest


@pytest.fixture
def auth_token(client):
    """使用不依赖 AppSecret 的游客路径获取测试 token。"""
    res = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": "profile-test-user"},
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


@pytest.mark.parametrize("method", ["patch", "put"])
def test_patch_account_trims_and_updates_public_profile(client, auth_token, method):
    response = getattr(client, method)(
        "/api/v1/profile/account",
        json={
            "nickname": "  饭饭  ",
            "avatar_url": "cloud://cloud-test.avatar/avatars/1/avatar.png",
        },
        headers=auth_token,
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "id": response.json()["data"]["id"],
        "nickname": "饭饭",
        "avatar_url": "cloud://cloud-test.avatar/avatars/1/avatar.png",
        "profile_complete": True,
    }

    refreshed = client.get("/api/v1/profile", headers=auth_token)
    assert refreshed.json()["data"]["nickname"] == "饭饭"
    assert refreshed.json()["data"]["avatar_url"].startswith("cloud://")


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({}, 422),
        ({"nickname": "   "}, 422),
        ({"nickname": "x" * 65}, 422),
        ({"avatar_url": "http://example.com/avatar.png"}, 422),
        ({"avatar_url": "javascript:alert(1)"}, 422),
    ],
)
def test_patch_account_rejects_invalid_public_profile(
    client,
    auth_token,
    payload,
    expected_status,
):
    response = client.patch(
        "/api/v1/profile/account",
        json=payload,
        headers=auth_token,
    )

    assert response.status_code == expected_status


def test_patch_account_only_updates_authenticated_user(client):
    first = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": "profile-owner", "nickname": "甲"},
    ).json()["data"]
    second = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": "profile-stranger", "nickname": "乙"},
    ).json()["data"]

    response = client.patch(
        "/api/v1/profile/account",
        json={"nickname": "甲改"},
        headers={"Authorization": f"Bearer {first['token']}"},
    )

    assert response.status_code == 200
    stranger = client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {second['token']}"},
    )
    assert stranger.json()["data"]["nickname"] == "乙"
