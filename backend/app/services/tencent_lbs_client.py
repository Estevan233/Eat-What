"""Tencent LBS WebService client with bounded grid caching.

学习点：
- 个人开发者地点搜索配额 200 次/日（2025-04-17 收紧），缓存节流是硬约束不是优化
- 缓存键用 3 位小数网格（约 100-200m）：同一商圈反复看不重复扣配额
- 新鲜 15 分钟；上游失败/限流时降级用 12 小时内陈旧结果并标 is_stale
- KEY 只从服务端环境变量读取，前端与代码包均不出现（PRD R7）
"""
import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.core.config import get_settings
from app.core.errors import ExternalAPIError, RateLimitError
from app.schemas.nearby import NearbyShop, NearbyShopsResponse

log = structlog.get_logger()

BASE_URL = "https://apis.map.qq.com/ws/place/v1/search"
DEFAULT_RADIUS_M = 1000
DEFAULT_KEYWORD = "美食"


def unavailable_shops(message: str = "附近店铺服务未配置") -> NearbyShopsResponse:
    """Neutral result: explicitly not presented as live POI data."""
    return NearbyShopsResponse(
        provider_available=False,
        source="unavailable",
        shops=[],
        fetched_at=datetime.now(timezone.utc),
    )


class TencentLbsClient:
    """腾讯位置服务 WebService 代理客户端（进程内网格缓存）。"""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float | None = None,
        fresh_cache_seconds: int | None = None,
        stale_cache_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        configured_key = settings.tencent_lbs_api_key
        resolved_key = (
            configured_key.get_secret_value()
            if api_key is None and configured_key is not None
            else api_key
        )
        self._api_key = resolved_key or ""
        self._timeout = timeout or settings.tencent_lbs_timeout_seconds
        self._fresh_cache_seconds = (
            settings.tencent_lbs_cache_ttl_seconds
            if fresh_cache_seconds is None
            else fresh_cache_seconds
        )
        self._stale_cache_seconds = (
            settings.tencent_lbs_stale_cache_seconds
            if stale_cache_seconds is None
            else stale_cache_seconds
        )
        self._cache: dict[tuple[str, int], tuple[datetime, NearbyShopsResponse]] = {}
        self._locks: dict[tuple[str, int], asyncio.Lock] = {}

    @staticmethod
    def _cache_key(keyword: str, lat: float, lng: float, radius_m: int) -> tuple[str, int]:
        return f"{keyword}:{round(lat, 3)},{round(lng, 3)}", radius_m

    def _cache_get(
        self,
        key: tuple[str, int],
        *,
        max_age_seconds: int,
    ) -> NearbyShopsResponse | None:
        cached = self._cache.get(key)
        if cached is None:
            return None
        cached_at, payload = cached
        age = (datetime.now(timezone.utc) - cached_at).total_seconds()
        if age <= max_age_seconds:
            return payload
        return None

    def _cache_put(self, key: tuple[str, int], payload: NearbyShopsResponse) -> None:
        self._cache[key] = (datetime.now(timezone.utc), payload)

    async def search_nearby_shops(
        self,
        lat: float,
        lng: float,
        *,
        keyword: str = DEFAULT_KEYWORD,
        radius_m: int = DEFAULT_RADIUS_M,
    ) -> NearbyShopsResponse:
        if not self._api_key:
            log.warning("tencent_lbs_missing_key")
            return unavailable_shops("服务端未配置 TENCENT_LBS_API_KEY")

        key = self._cache_key(keyword, lat, lng, radius_m)
        fresh = self._cache_get(key, max_age_seconds=self._fresh_cache_seconds)
        if fresh is not None:
            log.info("tencent_lbs_cache_hit", grid=key)
            return fresh

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            fresh = self._cache_get(key, max_age_seconds=self._fresh_cache_seconds)
            if fresh is not None:
                return fresh
            try:
                payload = await self._fetch(lat, lng, keyword=keyword, radius_m=radius_m)
            except (ExternalAPIError, RateLimitError):
                stale = self._cache_get(key, max_age_seconds=self._stale_cache_seconds)
                if stale is None:
                    raise
                log.warning("tencent_lbs_stale_cache_hit", grid=key)
                return stale.model_copy(update={"source": "cache", "is_stale": True})
            self._cache_put(key, payload)
            return payload

    async def _fetch(
        self,
        lat: float,
        lng: float,
        *,
        keyword: str,
        radius_m: int,
    ) -> NearbyShopsResponse:
        params: dict[str, str] = {
            "keyword": keyword,
            "boundary": f"nearby({lat},{lng},{radius_m})",
            "page_size": "20",
            "page_index": "1",
            "key": self._api_key,
        }
        log.info("tencent_lbs_fetch_start", lat=round(lat, 3), lng=round(lng, 3))
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(BASE_URL, params=params)
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            log.warning("tencent_lbs_network_error", error_type=error_type)
            raise ExternalAPIError("tencent_lbs", f"网络异常({error_type})") from None

        if response.status_code == 429:
            raise RateLimitError("tencent_lbs")
        if response.status_code != 200:
            raise ExternalAPIError("tencent_lbs", f"HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalAPIError("tencent_lbs", f"非 JSON 响应: {type(exc).__name__}") from None

        status = int(payload.get("status", -1))
        if status != 0:
            message = str(payload.get("message", ""))
            if status == 121 or "达到上限" in message or "配额" in message:
                raise RateLimitError("tencent_lbs")
            raise ExternalAPIError("tencent_lbs", f"status={status} message={message or 'missing'}")
        return self._parse(payload)

    def _parse(self, payload: dict[str, Any]) -> NearbyShopsResponse:
        data = payload.get("data") or []
        if not isinstance(data, list):
            raise ExternalAPIError("tencent_lbs", "响应 data 字段无效")
        shops: list[NearbyShop] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            location = item.get("location") or {}
            lat = location.get("lat")
            lng = location.get("lng")
            if lat is None or lng is None:
                continue
            try:
                shops.append(
                    NearbyShop(
                        name=str(item.get("title", "")),
                        address=str(item.get("address", "")),
                        category=str(item.get("category", "")),
                        lat=float(lat),
                        lng=float(lng),
                        distance_m=int(item.get("_distance") or 0),
                    )
                )
            except (TypeError, ValueError):
                continue
        return NearbyShopsResponse(
            provider_available=True,
            source="tencent_lbs",
            shops=shops,
            fetched_at=datetime.now(timezone.utc),
        )


tencent_lbs_client = TencentLbsClient()
