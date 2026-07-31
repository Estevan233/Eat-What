"""今日上下文路由 - GET /context/today + POST /context/weather。

学习点：
- /today 公开无需登录（首页节气卡片）：用 service 层进程内缓存
- /weather 需登录（PRD：防滥用），POST body 含 lat/lng，调 Open-Meteo
- response_model 用 dict[str, Any] + success() 包
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.weather import WeatherData, WeatherRequest
from app.services.solar_terms import get_today_context_cached
from app.services.weather_client import weather_client
from app.utils.response import success

router = APIRouter(prefix="/context", tags=["context"])


@router.get("/today", response_model=dict[str, Any])
def get_today_context_route() -> dict[str, object]:
    """返回今日历法上下文（星座/生肖/节气/农历）。

    公开端点，无需登录。同一天进程内缓存命中，响应一致。
    """
    ctx = get_today_context_cached()
    return success(data=ctx.model_dump(mode="json"))


@router.post("/weather", response_model=dict[str, Any])
async def get_weather_route(
    body: WeatherRequest,
    user: User = Depends(get_current_user),
    _session: Session = Depends(get_db),
) -> dict[str, object]:
    """取当前坐标的实时天气。需登录。

    Body: {"lat": float, "lng": float}
    Returns: {"ok": true, "data": WeatherData}
    1h 内同坐标进程内缓存命中，不发外部 HTTP。
    """
    if user.id is None:  # pragma: no cover - DB 行必有 id
        raise RuntimeError("get_current_user 返回的 user.id 不应为 None")

    data = await weather_client.get_current(body.lat, body.lng)
    return success(data=data.model_dump(mode="json"))


# 给 WeatherData 类型在 __all__ 里留个导入别名（便于路由文件 import）
__all__ = ["WeatherData", "get_today_context_route", "get_weather_route", "router"]
