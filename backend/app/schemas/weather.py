"""天气数据 schema - 给推荐算法与 UI 当前实况。

学习点：
- weather_tag 是算法可用的离散值（6+1），由后端把和风 icon + 温度/湿度映射归类
- 字段命名后端 snake_case，前端 camelCase 由 request 层转换
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WeatherTag = Literal["cold", "hot", "rainy", "snowy", "dry", "mild", "any"]


class WeatherData(BaseModel):
    """POST /context/weather / GET 缓存返回的当前实况天气。"""

    model_config = ConfigDict(from_attributes=True)
    provider_available: bool = Field(
        default=True,
        description='是否来自可用的实时天气供应商；false 时 UI 不展示伪造温度',
    )

    source: Literal["qweather", "cache", "neutral"] = "neutral"
    is_stale: bool = False
    observed_at: datetime | None = None
    location_name: str
    temp_c: float = Field(description="当前温度 °C")
    feels_like_c: float = Field(description="体感温度 °C")
    text: str = Field(description="和风天气返回的晴/多云/小雨/雪/雷暴等描述")
    wind_dir: str = Field(description="风向 8 方位中文：北/东北/...")
    wind_scale: str = Field(description="蒲福风级，如 '1-3级' 或 '7-8级'")
    humidity: int = Field(ge=0, le=100, description="相对湿度 %")
    precipitation_mm: float = Field(ge=0, description="当前小时降水量 mm")
    weather_tag: WeatherTag
    fetched_at: datetime


class WeatherRequest(BaseModel):
    """POST /context/weather 请求体。"""

    lat: float = Field(..., ge=-90, le=90, description="纬度 WGS84")
    lng: float = Field(..., ge=-180, le=180, description="经度 WGS84")
