"""T08/T09 今日上下文 API 集成测。

T08 覆盖：
1. GET /context/today 公开无需登录 → 200
2. 返回 TodayContext JSON 含所有字段
3. 同一天重复调用一致（缓存）

T09 覆盖：
4. POST /context/weather 未登录 → 401
5. 登录后 + 合法坐标 → 200 + WeatherData 字段 + weather_tag 6+1
6. lat/lng 越界 → 422
7. mock weather_client 不真实联网
"""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def auth_token(client):
    """使用不依赖 AppSecret 的游客路径获取测试 token。"""
    res = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": "context-test-user"},
    )
    assert res.status_code == 200
    token = res.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_weather():
    """替换 weather_client 单例的 get_current 为 AsyncMock，返回一个雨天 mock。"""
    from datetime import datetime, timezone

    from app.schemas.weather import WeatherData
    from app.services import weather_client as mod

    sample = WeatherData(
        location_name="和风天气 @ 39.9,116.4",
        temp_c=22.5,
        feels_like_c=24.0,
        text="小雨",
        wind_dir="南",
        wind_scale="2级 轻风",
        humidity=78,
        precipitation_mm=1.5,
        weather_tag="rainy",
        fetched_at=datetime.now(timezone.utc),
    )
    # 单例的 get_current 是 async 方法，TestClient 同步调用流程会通过 ASGI 跑协程
    # AsyncMock 让 await 正常工作
    mod.weather_client.get_current = AsyncMock(return_value=sample)
    mod.weather_client.cache_clear()
    yield mod.weather_client
    # 测试结束无需还原（pytest fixture 之间互不影响）


def test_get_today_context_returns_full_payload(client):
    res = client.get("/api/v1/context/today")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    data = body["data"]

    # TodayContext 必须字段
    assert "date" in data
    assert "solar_term_current" in data
    assert "solar_term_next_name" in data
    assert "solar_term_next_date" in data
    assert "zodiac_sign" in data
    assert "animal" in data
    assert "lunar_month" in data
    assert "lunar_day" in data
    assert "is_leap_month" in data

    # 字段类型校验
    assert isinstance(data["date"], str)
    assert isinstance(data["solar_term_current"], str)
    assert isinstance(data["solar_term_next_name"], str)
    assert isinstance(data["zodiac_sign"], str)
    assert isinstance(data["animal"], str)
    assert isinstance(data["lunar_month"], int)
    assert isinstance(data["lunar_day"], int)
    assert isinstance(data["is_leap_month"], bool)

    # 非空校验：任何时候都有下一节气名
    assert data["solar_term_next_name"]
    assert data["zodiac_sign"]
    assert data["animal"]


def test_get_today_context_no_auth_needed(client):
    """食物/上下文端点公开，不带 token 也能访问。"""
    res = client.get("/api/v1/context/today")
    assert res.status_code == 200
    assert res.json().get("code") != "AUTH_ERROR"


def test_get_today_context_calls_are_consistent(client):
    """同一天两次调用响应一致（缓存生效）。"""
    # 清缓存（路由走 cached 版本）
    from app.services.solar_terms import _get_today_context_cached

    _get_today_context_cached.cache_clear()

    r1 = client.get("/api/v1/context/today")
    r2 = client.get("/api/v1/context/today")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # 两次 data 完全相同
    assert r1.json()["data"] == r2.json()["data"]


def test_get_today_context_zodiac_value_in_12_signs(client):
    """zodiac_sign 必须在 12 星座英文键内。"""
    res = client.get("/api/v1/context/today")
    sign = res.json()["data"]["zodiac_sign"]
    assert sign in {
        "aries",
        "taurus",
        "gemini",
        "cancer",
        "leo",
        "virgo",
        "libra",
        "scorpio",
        "sagittarius",
        "capricorn",
        "aquarius",
        "pisces",
    }


# ---- T09 weather API ----


def test_post_weather_unauthenticated_returns_401(client):
    """未登录 POST /context/weather → 401。"""
    res = client.post("/api/v1/context/weather", json={"lat": 39.92, "lng": 116.41})
    assert res.status_code == 401
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "AUTH_ERROR"


def test_post_weather_authenticated_returns_data(client, auth_token, mock_weather):
    """登录后 → 200 + WeatherData 完整 payload + weather_tag 在 6+1 集合。"""
    res = client.post(
        "/api/v1/context/weather",
        json={"lat": 39.92, "lng": 116.41},
        headers=auth_token,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    data = body["data"]

    # WeatherData 全部字段
    assert "location_name" in data
    assert "temp_c" in data
    assert "feels_like_c" in data
    assert "text" in data
    assert "wind_dir" in data
    assert "wind_scale" in data
    assert "humidity" in data
    assert "precipitation_mm" in data
    assert "weather_tag" in data
    assert "fetched_at" in data

    # mock 的天气值冒泡走到 API
    assert data["temp_c"] == 22.5
    assert data["text"] == "小雨"
    assert data["weather_tag"] == "rainy"

    # weather_tag 在 6+1 集合
    assert data["weather_tag"] in {
        "cold",
        "hot",
        "rainy",
        "snowy",
        "dry",
        "mild",
        "any",
    }


def test_post_weather_provider_timeout_returns_neutral_soft_fallback(
    client,
    auth_token,
    mock_weather,
):
    '''天气供应商超时不能拖垮首页，返回明确标记的中性软降级。'''
    from app.core.errors import ExternalAPIError

    mock_weather.get_current.side_effect = ExternalAPIError(
        'open-meteo',
        'ConnectTimeout',
    )

    res = client.post(
        '/api/v1/context/weather',
        json={'lat': 35.6833, 'lng': 139.75},
        headers=auth_token,
    )

    assert res.status_code == 200
    body = res.json()
    assert body['ok'] is True
    assert body['data']['provider_available'] is False
    assert body['data']['location_name'] == '天气暂不可用'
    assert body['data']['weather_tag'] == 'mild'


def test_post_weather_invalid_lat_returns_422(client, auth_token, mock_weather):
    """lat 越界（>90）→ 422。"""
    res = client.post(
        "/api/v1/context/weather",
        json={"lat": 200.0, "lng": 116.41},
        headers=auth_token,
    )
    assert res.status_code == 422


def test_post_weather_invalid_lng_returns_422(client, auth_token, mock_weather):
    """lng 越界（>180）→ 422。"""
    res = client.post(
        "/api/v1/context/weather",
        json={"lat": 39.92, "lng": 999.0},
        headers=auth_token,
    )
    assert res.status_code == 422


def test_post_weather_missing_lat_returns_422(client, auth_token, mock_weather):
    """lat 缺失 → 422。"""
    res = client.post(
        "/api/v1/context/weather",
        json={"lng": 116.41},
        headers=auth_token,
    )
    assert res.status_code == 422


def test_post_weather_calls_client_with_coords(client, auth_token, mock_weather):
    """天气端点应把 lat/lng（snake）原样传给 weather_client.get_current。"""
    res = client.post(
        "/api/v1/context/weather",
        json={"lat": 39.92, "lng": 116.41},
        headers=auth_token,
    )
    assert res.status_code == 200
    # 验证 mock 被调用过，且参数对
    mock_weather.get_current.assert_awaited()
    args, kwargs = mock_weather.get_current.call_args
    # 按位置参数：get_current(lat, lng)
    assert args == (39.92, 116.41) or kwargs.get("lat") == 39.92
