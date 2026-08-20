"""T11 收藏 API 集成测。

覆盖：
1. POST /favorite/{id} 未登录 → 401
2. POST /favorite/{id} food 不存在 → 404
3. POST /favorite/{id} 首次 → favorited=true
4. POST /favorite/{id} 再次 → favorited=false（toggle）
5. GET /favorite 空列表
6. GET /favorite 有数据
7. GET /favorite 分页
"""

import pytest

from app.models.food import Food


@pytest.fixture
def auth_token(client):
    """使用不依赖 AppSecret 的游客路径获取测试 token。"""
    res = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": "favorite-test-user"},
    )
    assert res.status_code == 200
    token = res.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seed_foods(client):
    """直接用 session 建 5 道菜，返回 food_ids。"""
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        foods = [
            Food(
                name=f"收藏测试菜{i}",
                category="stir_fry",
                ingredients_json=["食材"],
                calories_kcal_per_100g=100.0,
                nutrition_json={"protein_g": 5.0, "fat_g": 5.0, "carb_g": 10.0},
                nature="neutral",
                flavor_json=[],
                organ_meridians_json=[],
                suitable_constitutions_json=["pinghe"],
                suitable_weathers_json=["any"],
                forbidden_for_json=[],
                tags_json=["easy"],
                cooking_method="stir_fry",
                cooking_time_min=20,
            )
            for i in range(5)
        ]
        for f in foods:
            session.add(f)
        session.commit()
        for f in foods:
            session.refresh(f)
        food_ids = [f.id for f in foods if f.id is not None]
    finally:
        session.close()
    return food_ids


def test_toggle_unauthenticated_returns_401(client):
    """未登录 POST /favorite/{id} → 401。"""
    res = client.post("/api/v1/favorite/1")
    assert res.status_code == 401


def test_toggle_food_not_found_returns_404(client, auth_token):
    """收藏不存在的 food → 404。"""
    res = client.post("/api/v1/favorite/99999", headers=auth_token)
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_toggle_first_time_favorited_true(client, auth_token, seed_foods):
    """首次收藏 → favorited=true。"""
    food_id = seed_foods[0]
    res = client.post(f"/api/v1/favorite/{food_id}", headers=auth_token)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["food_id"] == food_id
    assert data["favorited"] is True


def test_toggle_second_time_favorited_false(client, auth_token, seed_foods):
    """再次 toggle → favorited=false（取消收藏）。"""
    food_id = seed_foods[0]
    client.post(f"/api/v1/favorite/{food_id}", headers=auth_token)
    res = client.post(f"/api/v1/favorite/{food_id}", headers=auth_token)
    assert res.status_code == 200
    assert res.json()["data"]["favorited"] is False


def test_toggle_third_time_favorited_true(client, auth_token, seed_foods):
    """第三次 toggle → favorited=true（重新收藏）。"""
    food_id = seed_foods[0]
    client.post(f"/api/v1/favorite/{food_id}", headers=auth_token)
    client.post(f"/api/v1/favorite/{food_id}", headers=auth_token)
    res = client.post(f"/api/v1/favorite/{food_id}", headers=auth_token)
    assert res.status_code == 200
    assert res.json()["data"]["favorited"] is True


def test_list_empty_returns_zero(client, auth_token):
    """无收藏时 GET /favorite → total=0。"""
    res = client.get("/api/v1/favorite", headers=auth_token)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 0
    assert data["items"] == []


def test_list_returns_favorited_foods(client, auth_token, seed_foods):
    """收藏 3 道后 GET /favorite → 3 条 + 含 Food 详情。"""
    for i in range(3):
        client.post(f"/api/v1/favorite/{seed_foods[i]}", headers=auth_token)

    res = client.get("/api/v1/favorite", headers=auth_token)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 3
    assert len(data["items"]) == 3
    # 每条含 Food 详情字段
    item = data["items"][0]
    assert "name" in item
    assert "category" in item
    assert "cooking_method" in item


def test_list_pagination(client, auth_token, seed_foods):
    """收藏 5 道后 size=2 分页 → page1 返 2 条 total=5。"""
    for fid in seed_foods:
        client.post(f"/api/v1/favorite/{fid}", headers=auth_token)

    res = client.get("/api/v1/favorite?page=1&size=2", headers=auth_token)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["size"] == 2

    res2 = client.get("/api/v1/favorite?page=3&size=2", headers=auth_token)
    assert res2.json()["data"]["total"] == 5
    assert len(res2.json()["data"]["items"]) == 1


def test_list_unauthenticated_returns_401(client):
    """未登录 GET /favorite → 401。"""
    res = client.get("/api/v1/favorite")
    assert res.status_code == 401


def test_list_invalid_size_returns_422(client, auth_token):
    """size=0 → 422, size=100 → 422。"""
    res1 = client.get("/api/v1/favorite?size=0", headers=auth_token)
    assert res1.status_code == 422
    res2 = client.get("/api/v1/favorite?size=100", headers=auth_token)
    assert res2.status_code == 422
