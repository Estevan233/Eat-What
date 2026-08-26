"""QWeather client contract tests; all HTTP is mocked."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.errors import ExternalAPIError, RateLimitError
from app.services.weather_client import QWeatherClient, classify_weather_tag

QWEATHER_SAMPLE = {
    "code": "200",
    "updateTime": "2026-08-25T22:35+08:00",
    "now": {
        "obsTime": "2026-08-25T22:30+08:00",
        "temp": "31",
        "feelsLike": "35",
        "icon": "305",
        "text": "小雨",
        "wind360": "180",
        "windDir": "南风",
        "windScale": "3",
        "windSpeed": "14",
        "humidity": "78",
        "precip": "0.8",
    },
}


def _response(status: int = 200, body: dict | str | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = body if isinstance(body, dict) else {}
    response.text = body if isinstance(body, str) else str(body or "")
    return response


def _async_client(response: MagicMock) -> tuple[MagicMock, AsyncMock]:
    get = AsyncMock(return_value=response)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=MagicMock(get=get))
    context.__aexit__ = AsyncMock(return_value=None)
    return context, get


@pytest.mark.parametrize(
    ("icon", "temp", "humidity", "precip", "text", "expected"),
    [
        (100, 25, 60, 0, "晴", "mild"),
        (305, 20, 80, 1, "小雨", "rainy"),
        (401, -2, 80, 2, "中雪", "snowy"),
        (100, 5, 60, 0, "晴", "cold"),
        (100, 30, 60, 0, "晴", "hot"),
        (104, 22, 25, 0, "阴", "dry"),
    ],
)
def test_classify_weather_tag(icon, temp, humidity, precip, text, expected):
    assert classify_weather_tag(icon, temp, humidity, precip, text=text) == expected


@pytest.mark.asyncio
async def test_get_current_uses_qweather_host_key_and_lng_lat_order():
    client = QWeatherClient(
        api_host="demo.re.qweatherapi.com",
        api_key="server-secret",
    )
    context, get = _async_client(_response(200, QWEATHER_SAMPLE))

    with patch("app.services.weather_client.httpx.AsyncClient", return_value=context):
        data = await client.get_current(39.92, 116.41)

    _, kwargs = get.call_args
    assert get.call_args.args[0] == "https://demo.re.qweatherapi.com/v7/weather/now"
    assert kwargs["headers"] == {"X-QW-Api-Key": "server-secret"}
    assert kwargs["params"]["location"] == "116.41,39.92"
    assert data.temp_c == 31
    assert data.feels_like_c == 35
    assert data.text == "小雨"
    assert data.wind_dir == "南风"
    assert data.wind_scale == "3级"
    assert data.weather_tag == "rainy"
    assert data.provider_available is True
    assert "和风天气" in data.location_name


@pytest.mark.asyncio
async def test_fresh_cache_uses_city_grid_and_avoids_second_call():
    client = QWeatherClient(api_host="demo.re.qweatherapi.com", api_key="secret")
    context, get = _async_client(_response(200, QWEATHER_SAMPLE))

    with patch("app.services.weather_client.httpx.AsyncClient", return_value=context):
        first = await client.get_current(39.9201, 116.4101)
        second = await client.get_current(39.9499, 116.4499)

    assert second == first
    assert get.call_count == 1


@pytest.mark.asyncio
async def test_provider_failure_uses_stale_cache_within_twelve_hours():
    client = QWeatherClient(api_host="demo.re.qweatherapi.com", api_key="secret")
    success_context, _ = _async_client(_response(200, QWEATHER_SAMPLE))
    with patch("app.services.weather_client.httpx.AsyncClient", return_value=success_context):
        expected = await client.get_current(39.92, 116.41)

    key = client._round_key(39.92, 116.41)
    client._cache[key] = (datetime.now(timezone.utc) - timedelta(hours=2), expected)
    failure_context = MagicMock()
    failure_context.__aenter__ = AsyncMock(side_effect=httpx.ConnectTimeout("timeout"))
    failure_context.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.weather_client.httpx.AsyncClient", return_value=failure_context):
        actual = await client.get_current(39.92, 116.41)

    assert actual.source == "cache"
    assert actual.is_stale is True
    assert actual.temp_c == expected.temp_c
    assert actual.text == expected.text
    assert actual.observed_at == expected.observed_at
    assert actual.fetched_at == expected.fetched_at


@pytest.mark.asyncio
async def test_application_rate_limit_raises_when_no_stale_cache():
    client = QWeatherClient(api_host="demo.re.qweatherapi.com", api_key="secret")
    context, _ = _async_client(_response(200, {"code": "429"}))

    with patch("app.services.weather_client.httpx.AsyncClient", return_value=context):
        with pytest.raises(RateLimitError):
            await client.get_current(39.92, 116.41)


@pytest.mark.asyncio
async def test_missing_server_credentials_fails_closed_without_leaking_key():
    client = QWeatherClient(api_host="", api_key="")

    with pytest.raises(ExternalAPIError) as exc_info:
        await client.get_current(39.92, 116.41)

    assert "未配置" in exc_info.value.message


@pytest.mark.asyncio
async def test_invalid_payload_raises_external_api():
    client = QWeatherClient(api_host="demo.re.qweatherapi.com", api_key="secret")
    context, _ = _async_client(_response(200, {"code": "200"}))

    with patch("app.services.weather_client.httpx.AsyncClient", return_value=context):
        with pytest.raises(ExternalAPIError) as exc_info:
            await client.get_current(39.92, 116.41)

    assert "now" in exc_info.value.message
