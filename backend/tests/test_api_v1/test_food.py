"""T07 食物库 API 集成测。

覆盖 PRD 验收：
1. GET /food?page=1&size=20 → 返回 20 条 + total
2. GET /food/{id} → 详情
3. GET /food/search?q=番茄 → 模糊搜索
4. GET /food 不存在 id → 404
5. GET /food/search 空 q → 422（pydantic min_length=1）
6. GET /food?category=soup → 过滤
7. size 越界（>50）→ 422
8. 食物库是公开端点，无需登录

学习点：
- 用 fixture 在每个测试前 seed 数据（_clean_tables autouse 会清表，所以 seed 在测试函数内）
- food 端点不需要 Authorization header（公开只读数据）
"""
import pytest

from app.services.food_seed import DEFAULT_SEED_PATH, import_seed
from app.services.recipe_seed import import_recipe_seed


@pytest.fixture
def seeded_session(session):
    """在测试用 session 里灌入 seed 数据，返回 session。

    注意：必须用 session fixture（与 client 共享同一 in-memory engine），
    这样 client 调 API 时能看到 seed 的数据。
    """
    import_seed(session, DEFAULT_SEED_PATH)
    import_recipe_seed(session)
    return session


def test_list_food_returns_paginated(client, seeded_session):
    res = client.get("/api/v1/food?page=1&size=20")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["page"] == 1
    assert data["size"] == 20
    assert data["total"] >= 30
    assert len(data["items"]) == 20
    # 字段名是干净的（无 _json 后缀）
    item = data["items"][0]
    assert "ingredients" in item
    assert "ingredients_json" not in item
    assert "nutrition" in item
    assert "suitable_constitutions" in item


def test_list_food_default_size(client, seeded_session):
    """不带 size 默认 20。"""
    res = client.get("/api/v1/food")
    assert res.status_code == 200
    assert len(res.json()["data"]["items"]) == 20


def test_list_food_size_too_large_returns_422(client, seeded_session):
    """size > 50 → 422（le=50 校验）。"""
    res = client.get("/api/v1/food?size=51")
    assert res.status_code == 422


def test_list_food_category_filter(client, seeded_session):
    """category=soup 只返回汤类。"""
    res = client.get("/api/v1/food?category=soup&size=50")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] > 0
    assert all(item["category"] == "soup" for item in data["items"])


def test_get_food_by_id(client, seeded_session):
    """按 id 取详情。"""
    # 先拿一个 id
    listing = client.get("/api/v1/food?size=1").json()["data"]["items"]
    fid = listing[0]["id"]

    res = client.get(f"/api/v1/food/{fid}")
    assert res.status_code == 200
    item = res.json()["data"]
    assert item["id"] == fid
    assert item["name"]
    assert "nutrition" in item


def test_get_food_by_id_not_found(client, seeded_session):
    """不存在的 id → 404。"""
    res = client.get("/api/v1/food/99999")
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "NOT_FOUND"


def test_search_food(client, seeded_session):
    """搜索「番茄」返回含番茄的菜。"""
    res = client.get("/api/v1/food/search?q=番茄")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["q"] == "番茄"
    assert len(data["items"]) >= 2
    assert all("番茄" in item["name"] for item in data["items"])


def test_search_food_empty_q_returns_422(client, seeded_session):
    """空 q → 422（min_length=1）。"""
    res = client.get("/api/v1/food/search?q=")
    assert res.status_code == 422


def test_search_food_missing_q_returns_422(client, seeded_session):
    """没传 q → 422（Query required）。"""
    res = client.get("/api/v1/food/search")
    assert res.status_code == 422


def test_food_endpoints_no_auth_needed(client, seeded_session):
    """食物端点公开，不带 token 也能访问。"""
    res = client.get("/api/v1/food?size=5")
    assert res.status_code == 200
    # 不应返回 401
    assert res.json().get("code") != "AUTH_ERROR"


def test_get_food_recipe(client, seeded_session):
    """结构化菜谱包含量化食材、4-6 步和每份营养。"""
    listing = client.get("/api/v1/food?size=50").json()["data"]["items"]
    seeded_recipe = next(item for item in listing if item["recipe_ready"])

    response = client.get(f"/api/v1/food/{seeded_recipe['id']}/recipe")

    assert response.status_code == 200
    recipe = response.json()["data"]
    assert recipe["food_id"] == seeded_recipe["id"]
    assert 4 <= len(recipe["steps"]) <= 6
    assert recipe["nutrition_per_serving"]["energy_kcal"] > 0
    assert all(ingredient["unit"] for ingredient in recipe["ingredients"])


def test_get_food_recipe_not_found(client, seeded_session):
    """存在但没有结构化菜谱的 Food 返回 404。"""
    listing = client.get("/api/v1/food?size=50").json()["data"]["items"]
    food_without_recipe = next(item for item in listing if not item["recipe_ready"])

    response = client.get(f"/api/v1/food/{food_without_recipe['id']}/recipe")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
