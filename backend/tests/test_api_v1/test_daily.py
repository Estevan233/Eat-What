"""T10 每日推荐 API 集成测。

覆盖：
1. POST /daily/recommend 未登录 → 401
2. 登录后无 profile → 404
3. 登录后有 profile 但无 foods → ValidationError(400)
4. 登录 + 有 profile + 有 foods → 200 + 3 道菜 + context
5. lat 越界 → 422
6. lng 越界 → 422
7. mood 非法 → 422
8. activity_level 非法 → 422
9. 推荐写入 DailyLog（recommended_food_ids）
10. lat/lng 提供时调 weather_client
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.models.food import Food
from app.schemas.weather import WeatherData
from app.services import recommender
from app.services.wx_client import Code2SessionResult


@pytest.fixture
def auth_token(client, monkeypatch):
    """登录拿 token。"""
    from app.services import wx_client as mod
    result: Code2SessionResult = {
        "openid": "openid_for_daily_test",
        "session_key": "fake",
        "unionid": None,
    }
    mod.wx_client.code2session = AsyncMock(return_value=result)
    res = client.post("/api/v1/auth/wx-login", json={"code": "fake"})
    assert res.status_code == 200
    token = res.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seed_profile_and_foods(client, auth_token):
    """建一个 profile + 5 道菜，返回 (user_id, food_ids)。"""
    # 取当前 user id（从 token payload 反查；通过 GET /profile 拿）
    res = client.get("/api/v1/profile", headers=auth_token)
    assert res.status_code == 200
    user_data = res.json()["data"]
    user_id = user_data["id"]

    # PUT 一个 profile（必填）
    client.put(
        "/api/v1/profile",
        json={
            "birthday": "1990-01-15",
            "gender": "male",
            "height_cm": 175,
            "weight_kg": 70.0,
            "forbidden_tags": [],
        },
        headers=auth_token,
    )

    # 直接用 session 建 foods（绕开 seed-food CLI）
    from app.db import SessionLocal
    session = SessionLocal()
    try:
        foods = [
            Food(
                name=f"测试菜{i}",
                category=["staple", "soup", "stir_fry", "steam", "cold_dish"][i],
                ingredients_json=["食材"],
                calories_kcal_per_100g=100.0,
                nutrition_json={"protein_g": 5.0 + i, "fat_g": 5.0, "carb_g": 10.0, "fiber_g": 1.0},
                nature="neutral",
                flavor_json=[],
                organ_meridians_json=[],
                suitable_constitutions_json=["pinghe"],
                suitable_weathers_json=["any"],
                forbidden_for_json=[],
                tags_json=["easy"],
                cooking_method=["boil", "soup", "stir_fry", "steam", "cold"][i],
                cooking_time_min=20,
                image_url=None,
                seasonal_solar_terms_json=[],
                description=f"测试菜{i}",
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

    return user_id, food_ids


@pytest.fixture
def mock_weather():
    """替换 weather_client 单例的 get_current。"""
    sample = WeatherData(
        location_name="Open-Meteo @ 39.92,116.41",
        temp_c=22.5,
        feels_like_c=24.0,
        text="温和",
        wind_dir="南",
        wind_scale="2级 轻风",
        humidity=50,
        precipitation_mm=0.0,
        weather_tag="mild",
        fetched_at=datetime.now(timezone.utc),
    )
    from app.services import weather_client as mod
    mod.weather_client.get_current = AsyncMock(return_value=sample)
    mod.weather_client.cache_clear()
    yield mod.weather_client


def test_recommend_unauthenticated_returns_401(client):
    """未登录 POST /daily/recommend → 401。"""
    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "neutral"},
    )
    assert res.status_code == 401
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "AUTH_ERROR"


def test_recommend_no_profile_returns_404(client, auth_token):
    """登录但未建档 → 404 NotFoundError。"""
    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "neutral"},
        headers=auth_token,
    )
    assert res.status_code == 404
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "NOT_FOUND"


def test_recommend_success_returns_three_foods(
    client, auth_token, seed_profile_and_foods, mock_weather, monkeypatch
):
    """登录 + profile + foods → 200 + 3 道菜 + context。"""
    # patch today_context（避免节气动态值影响测试）
    from datetime import date

    from app.schemas.today_context import TodayContext
    monkeypatch.setattr(
        recommender, "get_today_context_cached",
        lambda: TodayContext(
            date=date.today(),
            solar_term_current="",
            solar_term_next_name="立秋",
            solar_term_next_date="2026-08-07",
            zodiac_sign="leo",
            animal="马",
            lunar_month=7,
            lunar_day=15,
            is_leap_month=False,
        ),
    )

    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "neutral", "lat": 39.92, "lng": 116.41},
        headers=auth_token,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    data = body["data"]

    # 3 道菜
    assert len(data["foods"]) == 3
    for f in data["foods"]:
        assert f["id"]
        assert f["name"]
        assert f["category"]
        assert f["reason"]
        assert 0.0 <= f["score"] <= 100.0

    # context
    assert "weather" in data["context"]
    assert "today" in data["context"]
    assert data["context"]["weather"]["weather_tag"] == "mild"
    assert data["context"]["today"]["zodiac_sign"] == "leo"


def test_recommend_invalid_lat_returns_422(client, auth_token, mock_weather, monkeypatch):
    """lat 越界 → 422。"""
    # 先建一个 profile（否则会 404 而非 422）
    client.put(
        "/api/v1/profile",
        json={
            "birthday": "1990-01-15",
            "gender": "male",
            "forbidden_tags": [],
        },
        headers=auth_token,
    )
    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "neutral", "lat": 200.0, "lng": 116.41},
        headers=auth_token,
    )
    assert res.status_code == 422


def test_recommend_invalid_lng_returns_422(client, auth_token, mock_weather):
    """lng 越界 → 422。"""
    client.put(
        "/api/v1/profile",
        json={
            "birthday": "1990-01-15",
            "gender": "male",
            "forbidden_tags": [],
        },
        headers=auth_token,
    )
    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "neutral", "lat": 39.92, "lng": 999.0},
        headers=auth_token,
    )
    assert res.status_code == 422


def test_recommend_invalid_mood_returns_422(client, auth_token, mock_weather):
    """mood 非法值 → 422。"""
    client.put(
        "/api/v1/profile",
        json={
            "birthday": "1990-01-15",
            "gender": "male",
            "forbidden_tags": [],
        },
        headers=auth_token,
    )
    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "exhausted"},  # 非法
        headers=auth_token,
    )
    assert res.status_code == 422


def test_recommend_invalid_activity_level_returns_422(client, auth_token, mock_weather):
    """activity_level 非法值 → 422。"""
    client.put(
        "/api/v1/profile",
        json={
            "birthday": "1990-01-15",
            "gender": "male",
            "forbidden_tags": [],
        },
        headers=auth_token,
    )
    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "neutral", "activity_level": "extreme"},  # 非法
        headers=auth_token,
    )
    assert res.status_code == 422


def test_recommend_writes_daily_log(
    client, auth_token, seed_profile_and_foods, mock_weather, monkeypatch
):
    """推荐成功后 DailyLog 表写入 recommended_food_ids + mood。"""
    from datetime import date

    from app.schemas.today_context import TodayContext
    monkeypatch.setattr(
        recommender, "get_today_context_cached",
        lambda: TodayContext(
            date=date.today(),
            solar_term_current="",
            solar_term_next_name="立秋",
            solar_term_next_date="2026-08-07",
            zodiac_sign="leo",
            animal="马",
            lunar_month=7,
            lunar_day=15,
            is_leap_month=False,
        ),
    )

    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "tired", "lat": 39.92, "lng": 116.41},
        headers=auth_token,
    )
    assert res.status_code == 200

    # 反查 DailyLog
    from sqlmodel import select

    from app.db import SessionLocal
    from app.models.daily_log import DailyLog
    user_id = seed_profile_and_foods[0]
    session = SessionLocal()
    try:
        log = session.exec(
            select(DailyLog).where(DailyLog.user_id == user_id)
        ).first()
        assert log is not None
        assert log.mood == "tired"
        assert log.weather_tag == "mild"
        assert len(log.recommended_food_ids_json) == 3
    finally:
        session.close()


def test_recommend_fallback_weather_without_coords(
    client, auth_token, seed_profile_and_foods, mock_weather, monkeypatch
):
    """不传 lat/lng → weather_tag=mild，不打外部 HTTP。"""
    from datetime import date

    from app.schemas.today_context import TodayContext
    monkeypatch.setattr(
        recommender, "get_today_context_cached",
        lambda: TodayContext(
            date=date.today(),
            solar_term_current="",
            solar_term_next_name="立秋",
            solar_term_next_date="2026-08-07",
            zodiac_sign="leo",
            animal="马",
            lunar_month=7,
            lunar_day=15,
            is_leap_month=False,
        ),
    )

    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "neutral"},  # 不传 lat/lng
        headers=auth_token,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["context"]["weather"]["weather_tag"] == "mild"
    # weather_client 未被调用
    mock_weather.get_current.assert_not_called()


def test_recommend_calls_weather_client_with_coords(
    client, auth_token, seed_profile_and_foods, mock_weather, monkeypatch
):
    """传 lat/lng 时调 weather_client.get_current。"""
    from datetime import date

    from app.schemas.today_context import TodayContext
    monkeypatch.setattr(
        recommender, "get_today_context_cached",
        lambda: TodayContext(
            date=date.today(),
            solar_term_current="",
            solar_term_next_name="立秋",
            solar_term_next_date="2026-08-07",
            zodiac_sign="leo",
            animal="马",
            lunar_month=7,
            lunar_day=15,
            is_leap_month=False,
        ),
    )

    res = client.post(
        "/api/v1/daily/recommend",
        json={"mood": "neutral", "lat": 39.92, "lng": 116.41},
        headers=auth_token,
    )
    assert res.status_code == 200
    mock_weather.get_current.assert_awaited_once_with(39.92, 116.41)
