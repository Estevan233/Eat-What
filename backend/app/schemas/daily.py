"""推荐相关 schema - 请求/响应模型。

学习点：
- RecommendRequest 是用户每日推荐的输入：心情/活动量/位置
- RecommendResponse 含 3 道菜 + 上下文（天气 + 节气）
- FoodWithReason 在 Food.to_read_dict() 基础上加 reason / score
"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.meal import MealNutrition, MealRole, MealSnapshot, MealSubstitution
from app.schemas.today_context import TodayContext
from app.schemas.weather import WeatherData

Mood = Literal["happy", "neutral", "tired", "stressed", "anxious"]
ActivityLevel = Literal["light", "normal", "high"]
DiningMode = Literal["cook", "eat_out"]
Audience = Literal["personal", "family"]


class RecommendRequest(BaseModel):
    """POST /daily/recommend 请求体。"""

    mood: Mood = Field(default="neutral", description="今日心情")
    activity_level: ActivityLevel = Field(default="normal", description="活动量")
    lat: float | None = Field(default=None, ge=-90, le=90, description="纬度；缺省用天气 fallback")
    lng: float | None = Field(default=None, ge=-180, le=180, description="经度；缺省用天气 fallback")
    dining_mode: DiningMode = Field(default="cook", description="自己做或点外卖/到店吃")
    audience: Audience = Field(default="personal", description="个人或家庭")
    party_size: int = Field(default=1, ge=1, le=8, description="本次用餐人数")
    exclude_food_ids: list[int] = Field(
        default_factory=list,
        max_length=12,
        description="客户端最近展示的菜品，仅作轮换软排除",
    )
    weather_snapshot: WeatherData | None = Field(
        default=None,
        description="客户端刚获取的天气快照；服务端仅复用短时有效数据",
    )

    @field_validator("exclude_food_ids")
    @classmethod
    def normalize_exclude_food_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("排除菜品 id 必须为正整数")
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_party_size(self) -> "RecommendRequest":
        if self.audience == "personal" and self.party_size != 1:
            raise ValueError("个人模式人数必须为 1")
        if self.audience == "family" and self.party_size < 2:
            raise ValueError("家庭模式人数必须为 2-8")
        return self


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


class RecommendationWeightProfile(BaseModel):
    nutrition: int = 22
    seasonal_wellness: int = 18
    personal_family: int = 20
    preference_history: int = 15
    feasibility: int = 15
    diversity: int = 10
    weather_modifier_limit: int = 3


class RecommendResponse(BaseModel):
    """POST /daily/recommend 响应 data。"""

    model_config = ConfigDict(from_attributes=True)

    foods: list[FoodWithReason]
    recommendation_id: int
    primary_meal: MealSnapshot
    substitutions: list[MealSubstitution]
    substitution_notice: str | None = None
    engine: str
    context: RecommendContext
    weight_profile: RecommendationWeightProfile
    wellness_disclaimer: str


class ChooseRequest(BaseModel):
    """POST /daily/choose 请求体。"""

    # food_id 保留给已发布旧版；新客户端按推荐事件一次确认完整餐。
    food_id: int | None = Field(default=None, description="旧版单菜选择 id")
    recommendation_id: int | None = None
    selected_food_ids: list[int] | None = None
    substitutions: list["ChoiceSubstitution"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_choice_mode(self) -> "ChooseRequest":
        legacy = self.food_id is not None
        complete = self.recommendation_id is not None and self.selected_food_ids is not None
        if legacy == complete:
            raise ValueError("请提交 food_id，或 recommendation_id + selected_food_ids")
        return self


class ChoiceSubstitution(BaseModel):
    target_role: MealRole
    replacement_food_id: int


class DailyLogRead(BaseModel):
    """DailyLog 对外暴露的读模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    log_date: str
    recommended_food_ids: list[int]
    chosen_food_ids: list[int]
    recommendation_id: int | None = None
    recommended_meal: MealSnapshot | None = None
    chosen_meal: MealSnapshot | None = None
    chosen_total_nutrition: MealNutrition | None = None
    mood: str
    activity_level: str
    weather_tag: str | None = None
    dining_mode: DiningMode = "cook"
    audience: Audience = "personal"
    party_size: int = 1


class HistoryResponse(BaseModel):
    """GET /daily/history 响应 data。"""

    model_config = ConfigDict(from_attributes=True)

    items: list[DailyLogRead]
    total: int


class FavoriteToggleResponse(BaseModel):
    """POST/DELETE /favorite/{food_id} 响应 data。"""

    food_id: int
    favorited: bool
