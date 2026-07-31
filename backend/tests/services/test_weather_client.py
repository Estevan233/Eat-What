"""T09 Open-Meteo weather_client 单测 - mock httpx 不联网。

覆盖：
1. WMO 分类 / 蒲福风级 / 风向 8 方位 纯函数
2. classify_weather_tag 6+1 离散值正确归类
3. OpenMeteoClient: 解析响应 → WeatherData
4. 缓存命中：同坐标 1h 内第二次不发 HTTP
5. 429 → RateLimitError；500 → ExternalAPIError
6. 响应缺字段 → ExternalAPIError
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.errors import ExternalAPIError, RateLimitError
from app.services.weather_client import (
    OpenMeteoClient,
    beaufort_label,
    classify_weather_tag,
    wind_dir_label,
)

# ---- 纯函数：蒲福风级 ----

@pytest.mark.parametrize("speed,expected", [
    (0.0, "0级 无风"),
    (1.5, "1级 软风"),
    (10.0, "2级 轻风"),
    (20.0, "4级 和风"),
    (39.0, "6级 强风"),    # 38 < 39 < 49 → 6 级
    (50.0, "6级 强风"),    # 38 < 50 < 49? 49 < 50 ≤ 49 → 实际是 7 级
    (60.0, "7级 疾风"),
    (70.0, "8级 大风"),
    (100.0, "10级 狂风"),
    (200.0, "12级 飓风"),
])
def test_beaufort_label(speed, expected):
    # 修正预期：50 在 38-49 区间外，是 7 级 强风（< 61 是 7 级）
    actual = beaufort_label(speed)
    if speed == 50.0:
        assert actual == "7级 疾风"
    else:
        assert actual == expected


# ---- 纯函数：风向 8 方位 ----

@pytest.mark.parametrize("deg,expected", [
    (0.0, "北"),
    (45.0, "东北"),
    (90.0, "东"),
    (135.0, "东南"),
    (180.0, "南"),
    (225.0, "西南"),
    (270.0, "西"),
    (315.0, "西北"),
    (360.0, "北"),    # 归一
    (337.5, "北"),    # 跨界归
    (22.5, "东北"),   # 边界 +22.5
])
def test_wind_dir_label(deg, expected):
    assert wind_dir_label(deg) == expected


# ---- 纯函数：weather_tag 归类 ----

@pytest.mark.parametrize("code,temp,humid,precip,expected", [
    (0, 25, 60, 0, "mild"),     # 晴 温和
    (71, -5, 80, 2, "snowy"),    # 小雪
    (75, -10, 80, 6, "snowy"),   # 大雪
    (-100, -3, 80, 6, "snowy"),  # 非 WMO 但 -3°C + 6mm 降水（按规则）
    (61, 20, 80, 1, "rainy"),    # 小雨
    (0, 5, 60, 0, "cold"),       # 晴 但 5°C → cold（先于 hot）
    (0, -2, 60, 0, "cold"),      # 0 下也 cold（无雪）
    (0, 30, 60, 0, "hot"),       # 28+ → hot
    (3, 22, 25, 0, "dry"),       # 阴 22°C + 湿度低 + 无雨 → dry
])
def test_classify_weather_tag(code, temp, humid, precip, expected):
    actual = classify_weather_tag(code, temp, humid, precip)
    assert actual == expected


def test_classify_priority_snow_over_rain():
    """雪优先于雨：WMO code 75（大雪）应 snowy 不 rainy。"""
    assert classify_weather_tag(75, -2, 80, 10) == "snowy"


def test_classify_priority_rain_over_cold():
    """雨优先于 cold：8°C + 小雨 → rainy，不是 cold。"""
    assert classify_weather_tag(63, 8, 80, 1.5) == "rainy"


# ---- OpenMeteoClient: mock 响应解析 ----

OPEN_METEO_RESPONSE_SAMPLE = {
    "latitude": 39.964848,
    "longitude": 116.39665,
    "timezone": "Asia/Shanghai",
    "utc_offset_seconds": 28800,
    "elevation": 49.0,
    "current_units": {
        "time": "iso8601",
        "interval": "seconds",
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "apparent_temperature": "°C",
        "weather_code": "wmo code",
        "wind_speed_10m": "km/h",
        "wind_direction_10m": "°",
    },
    "current": {
        "time": "2026-07-31T12:00",
        "interval": 900,
        "temperature_2m": 32.7,
        "relative_humidity_2m": 61,
        "apparent_temperature": 37.6,
        "weather_code": 51,    # 毛毛雨
        "wind_speed_10m": 8.5,
        "wind_direction_10m": 193,
    },
}


def _mock_resp(status: int = 200, body: dict | str | None = None) -> MagicMock:
    """构造 httpx.Response mock。"""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body if isinstance(body, dict) else {}
    resp.text = body if isinstance(body, str) else str(body or "")
    return resp


def _mock_async_client(resp: MagicMock) -> MagicMock:
    """构造 httpx.AsyncClient mock，GET 永远返回 resp。"""
    client_cm = AsyncMock()
    client_cm.__aenter__.return_value = MagicMock()
    client_cm.__aenter__.return_value.get = AsyncMock(return_value=resp)
    return client_cm


@pytest.mark.asyncio
async def test_get_current_parses_response_into_weather_data():
    """mock Open-Meteo success → WeatherData 字段正确。"""
    client = OpenMeteoClient()
    client.cache_clear()

    resp = _mock_resp(200, OPEN_METEO_RESPONSE_SAMPLE)
    with patch("app.services.weather_client.httpx.AsyncClient", return_value=_mock_async_client(resp)):
        data = await client.get_current(39.92, 116.41)

    assert data.temp_c == 32.7
    assert data.feels_like_c == 37.6
    assert data.humidity == 61
    assert data.text == "小雨"  # WMO 51 → 小雨
    assert data.wind_dir == "南"  # 193° → South
    assert data.wind_scale == "2级 轻风"  # 8.5 km/h
    # WMO 51 是雨类，precipitation 缺失默认 0，但 code 51 在 WMO_RAIN_CODES → rainy
    assert data.weather_tag == "rainy"
    assert "Open-Meteo" in data.location_name
    assert "39.92" in data.location_name
    assert isinstance(data.fetched_at, datetime)


@pytest.mark.asyncio
async def test_get_current_caches_within_ttl():
    """同坐标 1h 内第二次命中缓存，不发 HTTP。"""
    client = OpenMeteoClient()
    client.cache_clear()

    resp = _mock_resp(200, OPEN_METEO_RESPONSE_SAMPLE)
    mock_get = AsyncMock(return_value=resp)
    async_cm = _mock_async_client(resp)
    async_cm.__aenter__.return_value.get = mock_get

    with patch("app.services.weather_client.httpx.AsyncClient", return_value=async_cm):
        await client.get_current(39.92, 116.41)
        # 再次同坐标：
        await client.get_current(39.92, 116.41)

    # 只发一次 HTTP get
    assert mock_get.call_count == 1


@pytest.mark.asyncio
async def test_get_current_429_raises_rate_limit():
    """429 → RateLimitError。"""
    client = OpenMeteoClient()
    client.cache_clear()

    resp = _mock_resp(429, {"error": "Rate limit"})
    with patch("app.services.weather_client.httpx.AsyncClient", return_value=_mock_async_client(resp)):
        with pytest.raises(RateLimitError):
            await client.get_current(39.92, 116.41)


@pytest.mark.asyncio
async def test_get_current_500_raises_external_api():
    """500 → ExternalAPIError。"""
    client = OpenMeteoClient()
    client.cache_clear()

    resp = _mock_resp(500, "Server error")
    with patch("app.services.weather_client.httpx.AsyncClient", return_value=_mock_async_client(resp)):
        with pytest.raises(ExternalAPIError) as exc_info:
            await client.get_current(39.92, 116.41)
        assert "500" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_get_current_network_error_raises_external_api():
    """httpx.HTTPError → ExternalAPIError。"""
    client = OpenMeteoClient()
    client.cache_clear()

    def raise_http_error(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    async_cm = MagicMock()
    async_cm.__aenter__ = AsyncMock(side_effect=raise_http_error)

    with patch("app.services.weather_client.httpx.AsyncClient", return_value=async_cm):
        with pytest.raises(ExternalAPIError) as exc_info:
            await client.get_current(39.92, 116.41)
        assert "网络" in str(exc_info.value.message) or "connection" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_get_current_missing_current_field_raises_external_api():
    """响应缺 current 字段 → ExternalAPIError。"""
    client = OpenMeteoClient()
    client.cache_clear()

    resp = _mock_resp(200, {"latitude": 0, "longitude": 0})  # 无 current
    with patch("app.services.weather_client.httpx.AsyncClient", return_value=_mock_async_client(resp)):
        with pytest.raises(ExternalAPIError) as exc_info:
            await client.get_current(39.92, 116.41)
        assert "current" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_cache_rounds_to_6_digits():
    """缓存 key 取 6 位小数 round：39.9200000001 与 39.92 共用缓存。"""
    client = OpenMeteoClient()
    client.cache_clear()

    resp = _mock_resp(200, OPEN_METEO_RESPONSE_SAMPLE)
    mock_get = AsyncMock(return_value=resp)
    async_cm = _mock_async_client(resp)
    async_cm.__aenter__.return_value.get = mock_get

    with patch("app.services.weather_client.httpx.AsyncClient", return_value=async_cm):
        await client.get_current(39.9200000001, 116.4100000001)
        await client.get_current(39.92, 116.41)
        await client.get_current(39.9200001, 116.4100001)

    # 全部用 round 后的同一 key，只发一次 HTTP
    assert mock_get.call_count == 1


if __name__ == "__main__":
    # 让 pytest 不报 asyncio_mode=auto 警告
    pass
