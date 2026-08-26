"""QWeather current conditions client with bounded server-side caching."""
import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.core.config import get_settings
from app.core.errors import ExternalAPIError, RateLimitError
from app.schemas.weather import WeatherData, WeatherTag

log = structlog.get_logger()

FRESH_CACHE_SECONDS = 3600
STALE_CACHE_SECONDS = 12 * 3600


def normalize_qweather_host(host: str) -> str:
    """Return a URL-safe QWeather API host without a trailing slash."""
    normalized = host.strip().rstrip("/")
    if not normalized:
        return ""
    if not normalized.startswith(("https://", "http://")):
        normalized = f"https://{normalized}"
    return normalized


def neutral_weather(*, location_name: str = "天气暂不可用") -> WeatherData:
    """Neutral algorithm input; it is explicitly not presented as live weather."""
    return WeatherData(
        provider_available=False,
        source="neutral",
        location_name=location_name,
        temp_c=22.0,
        feels_like_c=22.0,
        text="暂不可用",
        wind_dir="无",
        wind_scale="0级 无风",
        humidity=50,
        precipitation_mm=0.0,
        weather_tag="mild",
        fetched_at=datetime.now(timezone.utc),
    )


def classify_weather_tag(
    icon_code: int,
    temp_c: float,
    humidity: int,
    precipitation_mm: float,
    *,
    text: str = "",
) -> WeatherTag:
    """Map QWeather icon/current values to the small ranking vocabulary."""
    if 400 <= icon_code < 500 or "雪" in text or "冰粒" in text:
        return "snowy"
    if (
        300 <= icon_code < 400
        or precipitation_mm > 0.5
        or any(token in text for token in ("雨", "雷暴"))
    ):
        return "rainy"
    if temp_c < 10:
        return "cold"
    if temp_c >= 28:
        return "hot"
    if humidity < 35 and precipitation_mm == 0:
        return "dry"
    return "mild"


def _number(value: Any, *, default: float = 0.0) -> float:
    if value in (None, "", "-"):
        return default
    return float(value)


class QWeatherClient:
    """QWeather API client.

    Cache keys use a 0.1-degree city grid. Fresh data is reused for one hour;
    provider failures may reuse the last observation for up to twelve hours.
    """

    def __init__(
        self,
        *,
        api_host: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        fresh_cache_seconds: int = FRESH_CACHE_SECONDS,
        stale_cache_seconds: int = STALE_CACHE_SECONDS,
    ) -> None:
        settings = get_settings()
        configured_key = settings.qweather_api_key
        resolved_key = (
            configured_key.get_secret_value()
            if api_key is None and configured_key is not None
            else api_key
        )
        self._base_url = normalize_qweather_host(
            settings.qweather_api_host if api_host is None else api_host
        )
        self._api_key = resolved_key or ""
        self._timeout = timeout or settings.qweather_timeout_seconds
        self._fresh_cache_seconds = fresh_cache_seconds
        self._stale_cache_seconds = stale_cache_seconds
        self._cache: dict[tuple[float, float], tuple[datetime, WeatherData]] = {}
        self._locks: dict[tuple[float, float], asyncio.Lock] = {}

    @staticmethod
    def _round_key(lat: float, lng: float) -> tuple[float, float]:
        return round(lat, 1), round(lng, 1)

    def _cache_get(
        self,
        key: tuple[float, float],
        *,
        max_age_seconds: int,
    ) -> WeatherData | None:
        cached = self._cache.get(key)
        if cached is None:
            return None
        cached_at, weather = cached
        age = (datetime.now(timezone.utc) - cached_at).total_seconds()
        if age <= max_age_seconds:
            return weather
        return None

    def _cache_put(self, key: tuple[float, float], weather: WeatherData) -> None:
        self._cache[key] = (datetime.now(timezone.utc), weather)

    def cache_clear(self) -> None:
        self._cache.clear()

    async def get_current(self, lat: float, lng: float) -> WeatherData:
        key = self._round_key(lat, lng)
        fresh = self._cache_get(key, max_age_seconds=self._fresh_cache_seconds)
        if fresh is not None:
            log.info("weather_cache_hit", provider="qweather", grid=key)
            return fresh
        if not self._base_url or not self._api_key:
            raise ExternalAPIError("qweather", "服务端未配置 QWEATHER_API_HOST/API_KEY")

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            fresh = self._cache_get(key, max_age_seconds=self._fresh_cache_seconds)
            if fresh is not None:
                return fresh
            try:
                weather = await self._fetch(lat, lng, key)
            except (ExternalAPIError, RateLimitError):
                stale = self._cache_get(key, max_age_seconds=self._stale_cache_seconds)
                if stale is None:
                    raise
                log.warning("weather_stale_cache_hit", provider="qweather", grid=key)
                return stale.model_copy(update={"source": "cache", "is_stale": True})
            self._cache_put(key, weather)
            return weather

    async def _fetch(
        self,
        lat: float,
        lng: float,
        grid: tuple[float, float],
    ) -> WeatherData:
        url = f"{self._base_url}/v7/weather/now"
        params = {
            # v7 城市实况坐标格式最多支持两位小数，顺序为经度,纬度。
            "location": f"{lng:.2f},{lat:.2f}",
            "lang": "zh",
            "unit": "m",
        }
        headers = {"X-QW-Api-Key": self._api_key}
        log.info("weather_fetch_start", provider="qweather", grid=grid)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            log.warning(
                "weather_network_error",
                provider="qweather",
                error_type=error_type,
                grid=grid,
            )
            raise ExternalAPIError("qweather", f"网络异常({error_type})") from None

        if response.status_code == 429:
            raise RateLimitError("qweather")
        if response.status_code != 200:
            raise ExternalAPIError("qweather", f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalAPIError("qweather", f"非 JSON 响应: {type(exc).__name__}") from None

        code = str(payload.get("code", ""))
        if code == "429":
            raise RateLimitError("qweather")
        if code != "200":
            raise ExternalAPIError("qweather", f"业务响应 code={code or 'missing'}")
        return self._parse(payload, grid)

    def _parse(
        self,
        payload: dict[str, Any],
        grid: tuple[float, float],
    ) -> WeatherData:
        now = payload.get("now")
        if not isinstance(now, dict):
            raise ExternalAPIError("qweather", "响应缺 now 字段")
        try:
            temp_c = _number(now["temp"])
            feels_like_c = _number(now["feelsLike"])
            icon_code = int(now["icon"])
            text = str(now["text"])
            humidity = int(_number(now["humidity"]))
            precipitation = _number(now.get("precip"))
            wind_dir = str(now["windDir"])
            wind_scale_value = str(now["windScale"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ExternalAPIError(
                "qweather",
                f"now 字段无效: {type(exc).__name__}",
            ) from None

        wind_scale = (
            wind_scale_value
            if wind_scale_value.endswith("级")
            else f"{wind_scale_value}级"
        )
        observed_at = None
        observed_value = now.get("obsTime") or payload.get("updateTime")
        if isinstance(observed_value, str):
            try:
                observed_at = datetime.fromisoformat(observed_value)
            except ValueError:
                observed_at = None
        weather = WeatherData(
            provider_available=True,
            source="qweather",
            is_stale=False,
            observed_at=observed_at,
            location_name=f"和风天气 @ {grid[0]:.1f},{grid[1]:.1f}",
            temp_c=temp_c,
            feels_like_c=feels_like_c,
            text=text,
            wind_dir=wind_dir,
            wind_scale=wind_scale,
            humidity=humidity,
            precipitation_mm=max(0.0, precipitation),
            weather_tag=classify_weather_tag(
                icon_code,
                temp_c,
                humidity,
                precipitation,
                text=text,
            ),
            fetched_at=datetime.now(timezone.utc),
        )
        log.info(
            "weather_fetch_ok",
            provider="qweather",
            grid=grid,
            tag=weather.weather_tag,
        )
        return weather


weather_client = QWeatherClient()
