"""推荐相关 schema - 请求/响应模型。

学习点：
- RecommendRequest 是用户每日推荐的输入：心情/活动量/位置
- RecommendResponse 含 3 道菜 + 上下文（天气 + 节气）
- FoodWithReason 在 Food.to_read_dict() 基础上加 reason / score
"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.today_context import TodayContext
from app.schemas.weather import WeatherData

Mood = Literal["happy", "neutral", "tired", "stressed", "anxious"]
ActivityLevel = Literal["light", "normal", "high"]


class RecommendRequest(BaseModel):
    """POST /daily/recommend 请求体。"""

    mood: Mood = Field(default="neutral", description="今日心情")
    activity_level: ActivityLevel = Field(default="normal", description="活动量")
    lat: float | None = Field(default=None, ge=-90, le=90, description="纬度；缺省用天气 fallback")
    lng: float | None = Field(default=None, ge=-180, le=180, description="经度；缺省用天气 fallback")


class FoodWithReason(BaseModel):
    """单条带理由的推荐结果。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    ingredients: list[str] = []
    calories_kcal_per_100g: float | None = None
    nutrition: dict[str, Any] = {}
    nature: str
    flavor: list[str] = []
    organ_meridians: list[str] = []
    suitable_constitutions: list[str] = []
    suitable_weathers: list[str] = []
    forbidden_for: list[str] = []
    tags: list[str] = []
    cooking_method: str
    cooking_time_min: int | None = None
    image_url: str | None = None
    seasonal_solar_terms: list[str] = []
    description: str | None = None
    # T10 新增
    reason: str = Field(description="自然语言推荐理由")
    score: float = Field(description="0-100 打分（含小数）")


class RecommendContext(BaseModel):
    """推荐结果附带的上下文，前端可展示天气与历法。"""

    model_config = ConfigDict(from_attributes=True)

    weather: WeatherData
    today: TodayContext


class RecommendResponse(BaseModel):
    """POST /daily/recommend 响应 data。"""

    model_config = ConfigDict(from_attributes=True)

    foods: list[FoodWithReason]
    context: RecommendContext
