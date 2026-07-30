"""T06 体质测试 API 集成测。

覆盖 PRD 验收 5 条：
1. 未登录 POST → 401
2. 登录后无档案 → POST submit → 404（要求先建档案）
3. 登录后先建档案 → POST 全 1 → 返回 pinghe；DB 有记录
4. POST 后 GET 一致
5. GET 无记录 → 404
6. GET /questions 无需登录 → 200 + 9 题 + 5 选项
7. POST 缺题 → 422（pydantic 通过 dict 校验，service 层校验体 422）

学习点：
- 复用 test_profile.py 的 auth_token fixture 模式：mock wx-login 拿 token
- POST/GET 都用带 Authorization header 的 TestClient 调
"""
from unittest.mock import AsyncMock

import pytest

from app.models.user_profile import UserProfile
from app.services.wx_client import Code2SessionResult


@pytest.fixture
def auth_token(client, monkeypatch):
    """构造登录成功场景，返回带 token 的 Authorization header。"""
    from app.services import wx_client as mod
    result: Code2SessionResult = {
        "openid": "openid_for_constitution_test",
        "session_key": "fake_session_key",
        "unionid": None,
    }
    mod.wx_client.code2session = AsyncMock(return_value=result)

    res = client.post("/api/v1/auth/wx-login", json={"code": "fake_code"})
    assert res.status_code == 200
    token = res.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


VALID_PROFILE = {
    "birthday": "1990-01-15",
    "gender": "male",
    "height_cm": 175,
    "weight_kg": 70.0,
    "forbidden_tags": [],
}


def _create_profile(client, auth_token) -> None:
    """登录用户先 PUT /profile 建档，否则提交体质会 404。"""
    res = client.put("/api/v1/profile", json=VALID_PROFILE, headers=auth_token)
    assert res.status_code == 200


# --- 验收 1: 未登录 POST → 401 ---


def test_submit_unauthenticated_returns_401(client):
    res = client.post(
        "/api/v1/profile/constitution",
        json={"answers": {str(i): 3 for i in range(1, 10)}},
    )
    assert res.status_code == 401
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "AUTH_ERROR"


# --- 验收 6: GET /questions 无需登录 ---


def test_questions_endpoint_no_auth_needed(client):
    res = client.get("/api/v1/profile/constitution/questions")
    assert res.status_code == 200
    data = res.json()["data"]
    assert "questions" in data
    assert "options" in data
    assert len(data["questions"]) == 9
    assert len(data["options"]) == 5
    # 题面是 ZYYXH/T157-2009 标准的固定 9 题
    assert data["questions"][0]["text"] == "您精力充沛吗？"
    assert data["questions"][1]["text"] == "您容易疲乏吗？"
    assert data["questions"][8]["text"] == "您过敏（鼻塞/皮疹）吗？"
    # 5 级 Likert
    assert data["options"][0] == {"value": 1, "label": "没有"}
    assert data["options"][4] == {"value": 5, "label": "总是"}


# --- 验收 2: 未建档直接 POST → 404 ---


def test_submit_without_profile_returns_404(client, auth_token):
    res = client.post(
        "/api/v1/profile/constitution",
        json={"answers": {str(i): 3 for i in range(1, 10)}},
        headers=auth_token,
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "NOT_FOUND"


# --- 验收 3: 建档 + POST 全 1 → pinghe；DB 有记录 ---


def test_submit_creates_and_returns_result(client, auth_token, session):
    _create_profile(client, auth_token)

    # 全 1：题1=1（反向 raw_pinghe=5 → norm=100）→ 主平和
    res = client.post(
        "/api/v1/profile/constitution",
        json={"answers": {str(i): 1 for i in range(1, 10)}},
        headers=auth_token,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["primary"] == "pinghe"
    assert data["secondary"] == []
    assert data["scores_normalized"]["pinghe"] == 100
    assert data["constitution_type_str"] == "pinghe"

    # DB 字段已写入
    from sqlmodel import select

    record = session.exec(
        select(UserProfile).where(UserProfile.user_id != -1)  # 拉任意一行
    ).first()
    assert record is not None
    assert record.constitution_type == "pinghe"
    assert record.constitution_scores is not None
    assert record.constitution_scores["pinghe"] == 100


# --- 验收 4: POST 后 GET 一致 ---


def test_submit_then_get_returns_same(client, auth_token):
    _create_profile(client, auth_token)

    # 题1=5 题2=5 其余 1 → 主 qixu
    answers = {str(i): 1 for i in range(1, 10)}
    answers["1"] = 5
    answers["2"] = 5
    res_post = client.post(
        "/api/v1/profile/constitution",
        json={"answers": answers},
        headers=auth_token,
    )
    assert res_post.status_code == 200
    posted_data = res_post.json()["data"]

    res_get = client.get("/api/v1/profile/constitution", headers=auth_token)
    assert res_get.status_code == 200
    fetched_data = res_get.json()["data"]

    # GET 应与 POST 返回的一致
    assert fetched_data["primary"] == posted_data["primary"]
    assert fetched_data["secondary"] == posted_data["secondary"]
    assert fetched_data["scores_normalized"] == posted_data["scores_normalized"]
    assert fetched_data["constitution_type_str"] == posted_data["constitution_type_str"]


# --- 验收 5: GET 无记录 → 404 ---


def test_get_without_prior_returns_404(client, auth_token):
    _create_profile(client, auth_token)

    res = client.get("/api/v1/profile/constitution", headers=auth_token)
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "NOT_FOUND"


# --- 验收 7: POST 缺题 → 422 ---


def test_submit_missing_question_returns_422(client, auth_token):
    _create_profile(client, auth_token)

    # 只传 8 题答案 → service judge() 抛 ValidationError → 422
    answers = {str(i): 3 for i in range(1, 9)}  # 8 题
    res = client.post(
        "/api/v1/profile/constitution",
        json={"answers": answers},
        headers=auth_token,
    )
    assert res.status_code == 422
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "VALIDATION_ERROR"


# --- 验收 8: 重新测试覆盖之前的体质 ---


def test_resubmit_overwrites_previous_result(client, auth_token):
    _create_profile(client, auth_token)

    # 第一次：全 1 → pinghe
    res1 = client.post(
        "/api/v1/profile/constitution",
        json={"answers": {str(i): 1 for i in range(1, 10)}},
        headers=auth_token,
    )
    assert res1.status_code == 200
    assert res1.json()["data"]["primary"] == "pinghe"

    # 第二次：题1=5 题2=5 其余 1 → qixu，覆盖 pinghe
    answers = {str(i): 1 for i in range(1, 10)}
    answers["1"] = 5
    answers["2"] = 5
    res2 = client.post(
        "/api/v1/profile/constitution",
        json={"answers": answers},
        headers=auth_token,
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["primary"] == "qixu"

    # GET 返回新结果，不是旧的
    res_get = client.get("/api/v1/profile/constitution", headers=auth_token)
    assert res_get.json()["data"]["primary"] == "qixu"
