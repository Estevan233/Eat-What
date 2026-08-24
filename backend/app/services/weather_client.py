"""Open-Meteo 天气 client - 坐标直查当前实况，进程内缓存 1 小时。

学习点：
- Open-Meteo 免 key 免注册，GET 坐标直查返回 JSON，无多个端点
- WMO weather code 是统一标准，自行映射中文描述
- 蒲福风级 + 8 方位风向：纯查表，不引第三方库
- weather_tag 是算法可用离散值，把 WMO code + 温度湿度归类到 6+1 种
- 进程内 dict+TTL 缓存，key 用 6 位小数 round（~11m 精度），同坐标 1h 内不重打
- 客户端实例化时调 get_settings()，便于测试用 monkeypatch 替换配置
"""
import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.core.config import get_settings
from app.core.errors import ExternalAPIError, RateLimitError
from app.schemas.weather import WeatherData, WeatherTag

log = structlog.get_logger()

# Open-Meteo current= 参数一次性拿所有需要的变量
_CURRENT_VARS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,"
    "wind_speed_10m,wind_direction_10m,precipitation"
)

# ---- WMO weather code → 中文描述 ----
# 详参 https://open-meteo.com/en/docs WMO weather interpretation codes
WMO_TEXT_MAP: dict[int, str] = {
    0: "晴", 1: "多云", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小雨", 53: "小雨", 55: "中雨",
    56: "冻雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪",
    77: "冰粒",
    80: "阵雨", 81: "阵雨", 82: "强阵雨",
    85: "阵雪", 86: "阵雪",
    95: "雷暴", 96: "雷暴冰雹", 99: "强雷暴冰雹",
}

WMO_SNOW_CODES = {71, 73, 75, 77, 85, 86}
WMO_RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}

# ---- 蒲福风级（km/h 范围 → 中文描述）----
# (max_kmh, label)
BEAUFORT_SCALE: tuple[tuple[float, str], ...] = (
    (1.0, "0级 无风"),
    (5.0, "1级 软风"),
    (11.0, "2级 轻风"),
    (19.0, "3级 微风"),
    (28.0, "4级 和风"),
    (38.0, "5级 清风"),
    (49.0, "6级 强风"),
    (61.0, "7级 疾风"),
    (74.0, "8级 大风"),
    (88.0, "9级 烈风"),
    (102.0, "10级 狂风"),
    (117.0, "11级 暴风"),
    (float("inf"), "12级 飓风"),
)

# ---- 风向 8 方位（deg → 中文方位）----
# 北/东北/东/东南/南/西南/西/西北
WIND_DIRECTIONS = ("北", "东北", "东", "东南", "南", "西南", "西", "西北")


def beaufort_label(speed_kmh: float) -> str:
    """按 km/h 返回蒲福风级中文标签。"""
    for max_kmh, label in BEAUFORT_SCALE:
        if speed_kmh < max_kmh:
            return label
    return "12级 飓风"


def wind_dir_label(deg: float) -> str:
    """180°/方位 8 等分，返回中文方位。"""
    deg = deg % 360.0
    # (deg + 22.5) / 45 简化边界对齐
    idx = int((deg + 22.5) // 45) % 8
    return WIND_DIRECTIONS[idx]


def neutral_weather(*, location_name: str = '天气暂不可用') -> WeatherData:
    '''外部天气不可用时的中性算法输入；明确标记，不冒充实时观测。'''
    return WeatherData(
        provider_available=False,
        location_name=location_name,
        temp_c=22.0,
        feels_like_c=22.0,
        text='暂不可用',
        wind_dir='无',
        wind_scale='0级 无风',
        humidity=50,
        precipitation_mm=0.0,
        weather_tag='mild',
        fetched_at=datetime.now(timezone.utc),
    )


def classify_weather_tag(
    weather_code: int,
    temp_c: float,
    humidity: int,
    precipitation_mm: float,
) -> WeatherTag:
    """把当前实况映射到 6+1 种 weather_tag。

    按优先级互斥判断：
    1. snowy：WMO code 雪类，或气温<0 且降水>5mm
    2. rainy：WMO code 雨类，或 precipitation > 0.5mm
    3. cold：temp_c < 10
    4. hot：temp_c >= 28
    5. dry：humidity < 35 且无降水
    6. mild：上述都不命中
    """
    if weather_code in WMO_SNOW_CODES or (temp_c < 0 and precipitation_mm > 5):
        return "snowy"
    if weather_code in WMO_RAIN_CODES or precipitation_mm > 0.5:
        return "rainy"
    if temp_c < 10:
        return "cold"
    if temp_c >= 28:
        return "hot"
    if humidity < 35 and precipitation_mm == 0:
        return "dry"
    return "mild"


class OpenMeteoClient:
    """Open-Meteo API 客户端 + 1h 进程内缓存。

    用法：
        client = OpenMeteoClient()            # 模块级单例
        data = await client.get_current(lat, lng)
    缓存 key 用 round(6) 坐标，避免近邻重复打 HTTP。
    """

    def __init__(self, *, timeout: float = 8.0, cache_ttl_seconds: int = 3600) -> None:
        self._settings = get_settings()
        self._base_url = self._settings.open_meteo_api
        self._timeout = timeout
        self._cache_ttl = cache_ttl_seconds
        # cache: (lat_r, lng_r) -> (fetched_at_utc, WeatherData)
        self._cache: dict[tuple[float, float], tuple[datetime, WeatherData]] = {}

    @staticmethod
    def _round_key(lat: float, lng: float) -> tuple[float, float]:
        """坐标 6 位小数 round（~11m），同区命中缓存。"""
        return (round(lat, 6), round(lng, 6))

    def _cache_get(self, key: tuple[float, float]) -> WeatherData | None:
        cached = self._cache.get(key)
        if cached is None:
            return None
        fetched_at, data = cached
        age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
        if age < self._cache_ttl:
            return data
        # 过期：删
        self._cache.pop(key, None)
        return None

    def _cache_put(self, key: tuple[float, float], data: WeatherData) -> None:
        self._cache[key] = (datetime.now(timezone.utc), data)

    def cache_clear(self) -> None:
        """测试用：清缓存后重打 HTTP。"""
        self._cache.clear()

    async def get_current(self, lat: float, lng: float) -> WeatherData:
        """按坐标取当前实况天气。1h 内同坐标命中缓存不发请求。

        Raises:
            ExternalAPIError: 网络/非 200/响应格式异常
            RateLimitError: 429
        """
        key = self._round_key(lat, lng)
        cached = self._cache_get(key)
        if cached is not None:
            log.info("weather_cache_hit", lat=lat, lng=lng)
            return cached

        params: dict[str, str | float] = {
            "latitude": lat,
            "longitude": lng,
            "current": _CURRENT_VARS,
            "timezone": "Asia/Shanghai",
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
        }
        log.info("weather_fetch_start", lat=lat, lng=lng, url=self._base_url)

        resp = await self._get_with_retry(params)
        if resp.status_code == 429:
            raise RateLimitError("open-meteo")
        if resp.status_code != 200:
            log.warning("weather_http_error", status=resp.status_code, body=resp.text[:200])
            raise ExternalAPIError("open-meteo", f"HTTP {resp.status_code}")

        try:
            data = resp.json()
        except ValueError as e:
            raise ExternalAPIError("open-meteo", f"非 JSON 响应: {e}") from None

        weather = self._parse(data, lat, lng)
        self._cache_put(key, weather)
        log.info("weather_fetch_ok", lat=lat, lng=lng, tag=weather.weather_tag)
        return weather

    async def _get_with_retry(
        self,
        params: dict[str, str | float],
        *,
        max_attempts: int = 2,
    ) -> httpx.Response:
        """带连接级重试的 GET。只重试连接失败（DNS/TLS/建连），
        不在超时上重试，避免叠加等待让调用方（推荐 3s 预算）雪上加霜。
        """
        last_exc: httpx.HTTPError | None = None
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    return await client.get(self._base_url, params=params)
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                # 连接级失败常是瞬时（DNS/TLS 抖动），退避后重试一次
                last_exc = e
                if attempt + 1 < max_attempts:
                    await asyncio.sleep(0.25 * (attempt + 1))
                    continue
                break
            except httpx.HTTPError as e:
                last_exc = e
                break

        error_type = type(last_exc).__name__ if last_exc else "HTTPError"
        error_detail = str(last_exc).strip() if last_exc else error_type
        log.warning(
            "weather_network_error",
            error_type=error_type,
            error=error_detail,
        )
        raise ExternalAPIError(
            "open-meteo",
            f"网络异常({error_type}): {error_detail}",
        ) from None

    def _parse(self, data: dict[str, Any], lat: float, lng: float) -> WeatherData:
        """把 Open-Meteo 响应解析为 WeatherData。字段缺失抛 ExternalAPIError。"""
        current = data.get("current")
        if not isinstance(current, dict):
            raise ExternalAPIError("open-meteo", f"响应缺 current 字段: {data}")

        try:
            temp_c = float(current["temperature_2m"])
            humidity = int(current["relative_humidity_2m"])
            feels_like_c = float(current["apparent_temperature"])
            weather_code = int(current["weather_code"])
            wind_speed = float(current["wind_speed_10m"])
            wind_dir_deg = float(current["wind_direction_10m"])
            precipitation = float(current.get("precipitation", 0.0))
        except KeyError as e:
            raise ExternalAPIError("open-meteo", f"current 缺字段 {e}: {current}") from None

        text = WMO_TEXT_MAP.get(weather_code, f"WMO code {weather_code}")
        tag = classify_weather_tag(weather_code, temp_c, humidity, precipitation)

        return WeatherData(
            location_name=f"Open-Meteo @ {lat:.4f},{lng:.4f}",
            temp_c=temp_c,
            feels_like_c=feels_like_c,
            text=text,
            wind_dir=wind_dir_label(wind_dir_deg),
            wind_scale=beaufort_label(wind_speed),
            humidity=humidity,
            precipitation_mm=precipitation,
            weather_tag=tag,
            fetched_at=datetime.now(timezone.utc),
        )


# 模块级单例 - 路由直接 import，测试 monkeypatch 替换
weather_client = OpenMeteoClient()
