"""三餐化日记与收藏升级的集成测。

覆盖：
1. 同一天早/中/晚三餐 recommendation 记录独立保存，互不覆盖
2. 同日同餐次推荐 upsert 覆盖、manual 自记永远追加（一餐多条）
3. POST /daily/logs/manual 落库 + PATCH 权限（recommendation 仅 meal_slot/note）+ DELETE
4. GET /daily/history streak_days 连续打卡
5. GET /daily/history?query= 关键词搜索（菜名/店名/备注）
6. 自定义收藏：添加 / 同名拒绝 / 改备注 / 搜索 / 删除
7. 外食小本 query 搜索
"""

from datetime import date, timedelta

import pytest
from sqlmodel import select

from app.models.daily_log import DailyLog
from app.services import daily_service


def _session_factory():
    """运行时取 monkeypatch 后的 SessionLocal（与测试内存库一致）。"""
    import app.db as db_module

    return db_module.SessionLocal()


@pytest.fixture
def auth_token(client):
    res = client.post("/api/v1/auth/guest-login", json={"guest_id": "diary-test-user"})
    assert res.status_code == 200
    token = res.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_id(client, auth_token):
    res = client.get("/api/v1/profile", headers=auth_token)
    assert res.status_code == 200
    return res.json()["data"]["id"]


def _add_log(user_id: int, **kwargs) -> DailyLog:
    session = _session_factory()
    try:
        record = DailyLog(
            user_id=user_id,
            log_date=kwargs.pop("log_date"),
            meal_slot=kwargs.pop("meal_slot", "lunch"),
            source=kwargs.pop("source", "recommendation"),
            recommended_food_ids_json=kwargs.pop("recommended_food_ids_json", []),
            chosen_food_ids_json=kwargs.pop("chosen_food_ids_json", []),
            **kwargs,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record
    finally:
        session.close()


def _delete_all_logs(user_id: int) -> None:
    session = _session_factory()
    try:
        for record in session.exec(select(DailyLog).where(DailyLog.user_id == user_id)).all():
            session.delete(record)
        session.commit()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 三餐独立保存 / upsert / 追加
# ---------------------------------------------------------------------------


def test_three_meal_slots_saved_independently(client, auth_token, user_id):
    """早/中/晚三条 recommendation 记录互不覆盖。"""
    _delete_all_logs(user_id)
    today = date.today()
    for slot in ("breakfast", "lunch", "dinner"):
        _add_log(
            user_id,
            log_date=today,
            meal_slot=slot,
            chosen_food_ids_json=[100, 200, 300],
        )
    res = client.get("/api/v1/daily/history?days=7", headers=auth_token)
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    slots = {item["meal_slot"] for item in items}
    assert slots == {"breakfast", "lunch", "dinner"}


def test_recommendation_upserts_same_slot_manual_appends(client, auth_token, user_id):
    """同日同餐次：recommendation upsert（2 条），manual 追加（2 条）。"""
    _delete_all_logs(user_id)
    today = date.today()
    session = _session_factory()
    try:
        # recommendation upsert：两次同 slot 记录合并为一行
        daily_service.record_recommendation(
            session,
            user_id,
            recommended_food_ids=[1, 2, 3],
            mood="neutral",
            activity_level="normal",
            weather_tag=None,
            engine="rules_v6",
            event_date=today,
            meal_slot="lunch",
            request_id=f"req-lunch-{today.isoformat()}-1",
        )
        daily_service.record_recommendation(
            session,
            user_id,
            recommended_food_ids=[4, 5, 6],
            mood="happy",
            activity_level="normal",
            weather_tag=None,
            engine="rules_v6",
            event_date=today,
            meal_slot="lunch",
            request_id=f"req-lunch-{today.isoformat()}-2",
        )
        recommendation_rows = session.exec(
            select(DailyLog).where(
                DailyLog.user_id == user_id,
                DailyLog.source == "recommendation",
            )
        ).all()
        assert len(recommendation_rows) == 1
        assert list(recommendation_rows[0].recommended_food_ids_json) == [4, 5, 6]

        # manual 永远追加
        daily_service.create_manual_log(
            session,
            user_id,
            log_date=today,
            meal_slot="lunch",
            dishes=[{"name": "小笼包", "kcal": 300}],
            note=None,
        )
        daily_service.create_manual_log(
            session,
            user_id,
            log_date=today,
            meal_slot="lunch",
            dishes=[{"name": "豆浆"}],
        )
        manual_rows = session.exec(
            select(DailyLog).where(
                DailyLog.user_id == user_id,
                DailyLog.source == "manual",
            )
        ).all()
        assert len(manual_rows) == 2
    finally:
        session.rollback()
        session.close()
        _delete_all_logs(user_id)


# ---------------------------------------------------------------------------
# manual CRUD + PATCH 权限
# ---------------------------------------------------------------------------


def test_manual_log_crud_and_patch_permissions(client, auth_token, user_id):
    """manual 全字段可改；recommendation 仅 meal_slot/note 生效。"""
    _delete_all_logs(user_id)
    today = date.today()

    # 1. manual 落库
    res = client.post(
        "/api/v1/daily/logs/manual",
        json={
            "log_date": today.isoformat(),
            "meal_slot": "breakfast",
            "dishes": [{"name": "小笼包", "kcal": 300}, {"name": "豆浆"}],
            "shop_name": "楼下早点铺",
            "note": "热乎",
        },
        headers=auth_token,
    )
    assert res.status_code == 200
    manual_entry = res.json()["data"]
    assert manual_entry["source"] == "manual"
    assert manual_entry["meal_slot"] == "breakfast"
    assert manual_entry["shop_name"] == "楼下早点铺"
    assert [dish["name"] for dish in manual_entry["manual_dishes"]] == ["小笼包", "豆浆"]

    # 2. manual PATCH：全字段生效
    res = client.patch(
        f"/api/v1/daily/logs/{manual_entry['id']}",
        json={
            "meal_slot": "lunch",
            "note": "改备注",
            "dishes": [{"name": "牛肉面", "kcal": 550}],
            "shop_name": "面馆",
        },
        headers=auth_token,
    )
    assert res.status_code == 200
    updated = res.json()["data"]
    assert updated["meal_slot"] == "lunch"
    assert updated["note"] == "改备注"
    assert updated["shop_name"] == "面馆"
    assert [dish["name"] for dish in updated["manual_dishes"]] == ["牛肉面"]

    # 3. recommendation PATCH：仅 meal_slot/note 生效
    rec_row = _add_log(
        user_id,
        log_date=today,
        meal_slot="dinner",
        chosen_food_ids_json=[9],
    )
    res = client.patch(
        f"/api/v1/daily/logs/{rec_row.id}",
        json={
            "note": "只改备注",
            "shop_name": "不应生效",
            "dishes": [{"name": "不应生效"}],
        },
        headers=auth_token,
    )
    assert res.status_code == 200
    rec_updated = res.json()["data"]
    assert rec_updated["note"] == "只改备注"
    assert rec_updated["shop_name"] is None

    # 4. DELETE
    res = client.delete(f"/api/v1/daily/logs/{manual_entry['id']}", headers=auth_token)
    assert res.status_code == 200
    res = client.get("/api/v1/daily/history?days=7", headers=auth_token)
    remaining_ids = {item["id"] for item in res.json()["data"]["items"]}
    assert manual_entry["id"] not in remaining_ids

    # 5. 删除他人的记录 → 404
    res = client.delete(f"/api/v1/daily/logs/{rec_row.id + 99999}", headers=auth_token)
    assert res.status_code == 404
    _delete_all_logs(user_id)


# ---------------------------------------------------------------------------
# streak + 搜索
# ---------------------------------------------------------------------------


def test_history_streak_days(client, auth_token, user_id):
    """连续打卡：今天+昨天有记录 → streak=2；今天没有 → 从昨天倒推不打断。"""
    _delete_all_logs(user_id)
    today = date.today()
    _add_log(user_id, log_date=today, meal_slot="lunch")
    _add_log(user_id, log_date=today - timedelta(days=1), meal_slot="dinner")
    res = client.get("/api/v1/daily/history?days=30", headers=auth_token)
    assert res.json()["data"]["streak_days"] == 2

    _delete_all_logs(user_id)
    _add_log(user_id, log_date=today - timedelta(days=1), meal_slot="lunch")
    _add_log(user_id, log_date=today - timedelta(days=2), meal_slot="dinner")
    res = client.get("/api/v1/daily/history?days=30", headers=auth_token)
    # 今天还没吃，连续天数保留（从昨天倒推）
    assert res.json()["data"]["streak_days"] == 2
    _delete_all_logs(user_id)


def test_history_query_search(client, auth_token, user_id):
    """搜索命中菜名/店名/备注；无结果时 items 为空。"""
    _delete_all_logs(user_id)
    today = date.today()
    _add_log(
        user_id,
        log_date=today,
        meal_slot="lunch",
        source="manual",
        shop_name="兰州拉面",
        note=None,
        chosen_meal_json={"dishes": [{"name": "牛肉拉面", "kcal": 500}]},
    )
    _add_log(
        user_id,
        log_date=today,
        meal_slot="dinner",
        source="manual",
        note="加班吃了轻食沙拉",
    )

    res = client.get("/api/v1/daily/history?days=7&query=拉面", headers=auth_token)
    items = res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["shop_name"] == "兰州拉面"

    res = client.get("/api/v1/daily/history?days=7&query=沙拉", headers=auth_token)
    assert len(res.json()["data"]["items"]) == 1

    res = client.get("/api/v1/daily/history?days=7&query=火锅", headers=auth_token)
    assert res.json()["data"]["items"] == []
    _delete_all_logs(user_id)


# ---------------------------------------------------------------------------
# 自定义收藏
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_foods(client):
    """直接用 session 建 2 道菜，返回 food_ids。"""
    from app.models.food import Food

    session = _session_factory()
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
            for i in range(2)
        ]
        for food in foods:
            session.add(food)
        session.commit()
        ids = [food.id for food in foods]
        return ids
    finally:
        session.close()


def test_custom_favorite_crud_and_search(client, auth_token, seed_foods):
    """自定义收藏全流程 + 与普通收藏共存 + 搜索。"""
    # 普通收藏一道
    res = client.post(f"/api/v1/favorite/{seed_foods[0]}", headers=auth_token)
    assert res.status_code == 200

    # 添加自定义收藏
    res = client.post(
        "/api/v1/favorite/custom",
        json={"custom_name": "楼下小王的番茄鸡蛋盖饭", "note": "少辣多汁"},
        headers=auth_token,
    )
    assert res.status_code == 200
    custom = res.json()["data"]
    assert custom["favorite_id"] is not None

    # 同名重复 → 422（项目内 ValidationError 统一映射 422）
    res = client.post(
        "/api/v1/favorite/custom",
        json={"custom_name": "楼下小王的番茄鸡蛋盖饭"},
        headers=auth_token,
    )
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION_ERROR"

    # 列表：普通 + 自定义共存
    res = client.get("/api/v1/favorite", headers=auth_token)
    items = res.json()["data"]["items"]
    assert res.json()["data"]["total"] == 2
    food_entry = next(item for item in items if item["food_id"] == seed_foods[0])
    custom_entry = next(
        item for item in items if item["custom_name"] == "楼下小王的番茄鸡蛋盖饭"
    )
    assert food_entry["food"] is not None
    assert custom_entry["food"] is None
    assert custom_entry["note"] == "少辣多汁"

    # 搜索命中自定义名
    res = client.get("/api/v1/favorite?query=番茄鸡蛋", headers=auth_token)
    items = res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["favorite_id"] == custom["favorite_id"]

    # 改备注
    res = client.patch(
        f"/api/v1/favorite/{custom['favorite_id']}",
        json={"note": "多加醋"},
        headers=auth_token,
    )
    assert res.status_code == 200
    assert res.json()["data"]["note"] == "多加醋"

    # 删除自定义收藏
    res = client.delete(f"/api/v1/favorite/{custom['favorite_id']}", headers=auth_token)
    assert res.status_code == 200
    res = client.get("/api/v1/favorite", headers=auth_token)
    assert res.json()["data"]["total"] == 1


# ---------------------------------------------------------------------------
# 外食小本搜索
# ---------------------------------------------------------------------------


def test_dining_memories_query_search(client, auth_token):
    """外食小本 query 过滤店名/菜名/备注。"""
    res = client.put(
        "/api/v1/dining/memories",
        json={"shop_name": "老王川菜馆", "dish_name": "麻婆豆腐", "verdict": "liked", "note": "下饭"},
        headers=auth_token,
    )
    assert res.status_code == 200
    res = client.put(
        "/api/v1/dining/memories",
        json={"shop_name": "沙县小吃", "dish_name": "蒸饺", "verdict": "avoided"},
        headers=auth_token,
    )
    assert res.status_code == 200

    res = client.get("/api/v1/dining/memories?query=川菜", headers=auth_token)
    items = res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["shop_name"] == "老王川菜馆"

    res = client.get("/api/v1/dining/memories?query=不存在的店", headers=auth_token)
    assert res.json()["data"]["items"] == []
