"""MVP E2E 烟测试 - 串起 login → profile → constitution → recommend → choose → favorite → history。

学习点：
- 用一个测试函数验证整个用户旅程，模块级单测覆盖不到的"流程连贯性"
- 全程 in-memory SQLite + mock wx code2session + mock weather + patched today_context
- 每步断言关键字段；不通过即整体 MVP 报错
"""
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.models.food import Food
from app.schemas.today_context import TodayContext
from app.schemas.weather import WeatherData
from app.services import recommender
from app.services import weather_client as wc_mod
from app.services.wx_client import Code2SessionResult

# 模拟一份北京温和天气
MOCK_WEATHER = WeatherData(
    location_name="Open-Meteo @ 39.92,116.41",
    temp_c=8.0,
    feels_like_c=5.0,
    text="晴",
    wind_dir="北",
    wind_scale="3级",
    humidity=40,
    precipitation_mm=0.0,
    weather_tag="cold",
    fetched_at=datetime.now(timezone.utc),
)

MOCK_TODAY = TodayContext(
    date=date.today(),
    solar_term_current="",
    solar_term_next_name="立秋",
    solar_term_next_date="2026-08-07",
    zodiac_sign="leo",
    animal="马",
    lunar_month=7,
    lunar_day=15,
    is_leap_month=False,
)


def _seed_foods(session) -> list[int]:
    """直接走 session 建 8 道菜覆盖 5 种 cooking_method + 适合冷天/热天。"""
    foods = []
    for i, cm in enumerate(["boil", "soup", "stir_fry", "steam", "cold", "boil", "stir_fry", "steam"]):
        f = Food(
            name=f"烟测菜{i}",
            category="stir_fry" if cm in ("stir_fry",) else "soup" if cm == "soup" else "staple",
            ingredients_json=[],
            calories_kcal_per_100g=80.0 + i,
            nutrition_json={"protein_g": 8.0 + i, "fat_g": 5.0, "carb_g": 10.0},
            nature="warm" if i % 2 == 0 else "neutral",
            flavor_json=[],
            organ_meridians_json=[],
            suitable_constitutions_json=["pinghe"],
            suitable_weathers_json=["cold"] if i < 4 else ["any"],
            forbidden_for_json=[],
            tags_json=["easy"],
            cooking_method=cm,
            cooking_time_min=20,
            seasonal_solar_terms_json=["liqiu"] if i < 4 else [],
            description=f"烟测菜{i}",
        )
        session.add(f)
        foods.append(f)
    session.commit()
    for f in foods:
        session.refresh(f)
    return [f.id for f in foods if f.id is not None]  # type: ignore[misc]


@pytest.fixture
def setup_app(client, monkeypatch):
    # mock wx code2session
    from app.services import wx_client
    result: Code2SessionResult = {"openid": "e2e_user", "session_key": "fake", "unionid": None}
    wx_client.wx_client.code2session = AsyncMock(return_value=result)

    # mock weather
    wc_mod.weather_client.get_current = AsyncMock(return_value=MOCK_WEATHER)
    wc_mod.weather_client.cache_clear()

    # mock 今天节气上下文
    monkeypatch.setattr(recommender, "get_today_context_cached", lambda: MOCK_TODAY)

    return client


@pytest.fixture
def authed(client, setup_app) -> dict[str, str]:
    res = client.post("/api/v1/auth/wx-login", json={"code": "fake"})
    assert res.status_code == 200, res.json()
    token = res.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_ids(session) -> list[int]:

    return _seed_foods(session)


def test_mvp_e2e_flow(client, authed, seeded_ids):
    """MVP 全流程: 登录 → 建档 → 体质 → 节气 → 推荐 → 选择 → 收藏 → 历史。"""

    # 1. 建档
    res = client.put(
        "/api/v1/profile",
        json={"birthday": "1992-07-15", "gender": "male", "forbidden_tags": ["pork"]},
        headers=authed,
    )
    assert res.status_code == 200
    assert res.json()["data"]["forbidden_tags"] == ["pork"]

    # 2. 体质测试 (求最小有效问卷答条)
    res = client.get("/api/v1/profile/constitution/questions", headers=authed)
    assert res.status_code == 200
    questions = res.json()["data"]["questions"]
    assert len(questions) == 9
    # 提交：全 1 → 主平和（Pinghe）
    answers = {str(q["id"]): 1 for q in questions}
    res = client.post(
        "/api/v1/profile/constitution",
        json={"answers": answers},
        headers=authed,
    )
    assert res.status_code == 200
    const_data = res.json()["data"]
    assert "constitution_type_str" in const_data

    # 3. 历法上下文（公开 API）
    res = client.get("/api/v1/context/today")
    assert res.status_code == 200
    today_data = res.json()["data"]
    assert "zodiac_sign" in today_data

    # 4. 推荐
    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "tired", "activity_level": "high", "lat": 39.92, "lng": 116.41},
        headers=authed,
    )
    assert res.status_code == 200
    rec_data = res.json()["data"]
    foods = rec_data["foods"]
    assert len(foods) == 3
    chosen_ids = [f["id"] for f in foods]
    for f in foods:
        assert "reason" in f
        assert 0.0 <= f["score"] <= 100.0
    assert rec_data["context"]["weather"]["weather_tag"] == "cold"

    # 5. 选第一道菜
    fid = chosen_ids[0]
    res = client.post(
        "/api/v1/daily/choose",
        json={"food_id": fid},
        headers=authed,
    )
    assert res.status_code == 200
    log = res.json()["data"]
    assert log["chosen_food_ids"] == [fid]

    # 6. GET /daily/today 显示已选
    res = client.get("/api/v1/daily/today", headers=authed)
    assert res.status_code == 200
    assert res.json()["data"]["chosen_food_ids"] == [fid]

    # 7. 收藏 toggle：food_id → favorited
    res = client.post(f"/api/v1/favorite/{fid}", headers=authed)
    assert res.status_code == 200
    assert res.json()["data"] == {"food_id": fid, "favorited": True}
    # 再点取消
    res = client.post(f"/api/v1/favorite/{fid}", headers=authed)
    assert res.status_code == 200
    assert res.json()["data"] == {"food_id": fid, "favorited": False}
    # 收藏另一道
    fid2 = chosen_ids[1]
    res = client.post(f"/api/v1/favorite/{fid2}", headers=authed)
    assert res.json()["data"]["favorited"] is True

    # 8. 收藏列表
    res = client.get("/api/v1/favorite", headers=authed)
    assert res.status_code == 200
    fav_data = res.json()["data"]
    assert fav_data["total"] == 1
    assert fav_data["items"][0]["id"] == fid2

    # 9. 历史列表含今天的记录
    res = client.get("/api/v1/daily/history?days=30", headers=authed)
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert items is not None
    assert any(it["chosen_food_ids"] == [fid] for it in items)

    # 10. 重新推荐（验证 DailyLog upsert 行为）- 再选不同心情
    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "happy", "activity_level": "light"},
        headers=authed,
    )
    assert res.status_code == 200
    assert len(res.json()["data"]["foods"]) == 3
