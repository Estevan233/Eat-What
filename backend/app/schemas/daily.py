"""推荐相关 schema - 请求/响应模型。

学习点：
- RecommendRequest 是用户每日推荐的输入：心情/活动量/位置
- RecommendResponse 含 3 道菜 + 上下文（天气 + 节气）
- FoodWithReason 在 Food.to_read_dict() 基础上加 reason / score
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.meal import MealNutrition, MealRole, MealSnapshot, MealSubstitution
from app.schemas.today_context import TodayContext
from app.schemas.weather import WeatherData

Mood = Literal["happy", "neutral", "tired", "stressed", "anxious"]
ActivityLevel = Literal["light", "normal", "high"]
DiningMode = Literal["cook", "eat_out"]
Audience = Literal["personal", "family"]
MealGoal = Literal["balanced", "weight_control", "high_protein"]
MealSlot = Literal["breakfast", "lunch", "dinner"]
LogSource = Literal["recommendation", "manual"]

MEAL_SLOT_VALUES: tuple[str, ...] = ("breakfast", "lunch", "dinner")


def infer_meal_slot(now: datetime | None = None) -> str:
    """按当前时间推断餐次（连续区间，无空档）：<10:30 早餐、<16:00 午餐、其余晚餐。"""
    moment = now or datetime.now()
    minutes = moment.hour * 60 + moment.minute
    if minutes < 10 * 60 + 30:
        return "breakfast"
    if minutes < 16 * 60:
        return "lunch"
    return "dinner"


class MealIntent(BaseModel):
    """AI 只负责抽取的结构化用餐意图；不接受菜品 ID 或营养结论。"""

    model_config = ConfigDict(extra="ignore")

    available_ingredients: list[str] = Field(default_factory=list, max_length=12)
    excluded_ingredients: list[str] = Field(default_factory=list, max_length=12)
    max_time_minutes: int | None = Field(default=None, ge=5, le=180)
    goal: MealGoal | None = None
    dining_mode_hint: DiningMode | None = None
    summary: str = Field(min_length=1, max_length=80)

    @field_validator("available_ingredients", "excluded_ingredients")
    @classmethod
    def normalize_ingredients(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_value in values:
            value = raw_value.strip()
            if not value:
                continue
            if len(value) > 24:
                raise ValueError("食材名称不能超过 24 个字符")
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(value)
        return normalized

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("用餐意图摘要不能为空")
        return normalized


class RecommendRequest(BaseModel):
    """POST /daily/recommend 请求体。"""

    request_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description='客户端生成的幂等请求号；网络重试复用同一值',
    )
    mood: Mood = Field(default="neutral", description="今日心情")
    activity_level: ActivityLevel = Field(default="normal", description="活动量")
    lat: float | None = Field(default=None, ge=-90, le=90, description="纬度；缺省用天气 fallback")
    lng: float | None = Field(default=None, ge=-180, le=180, description="经度；缺省用天气 fallback")
    dining_mode: DiningMode = Field(default="cook", description="自己做或点外卖/到店吃")
    audience: Audience = Field(default="personal", description="个人或家庭")
    party_size: int = Field(default=1, ge=1, le=8, description="本次用餐人数")
    exclude_food_ids: list[int] = Field(
        default_factory=list,
        max_length=36,
        description="客户端最近展示的菜品，仅作轮换软排除",
    )
    weather_snapshot: WeatherData | None = Field(
        default=None,
        description="客户端刚获取的天气快照；服务端仅复用短时有效数据",
    )
    meal_intent: MealIntent | None = Field(
        default=None,
        description="可选的结构化用餐意图；旧客户端不传时行为不变",
    )
    meal_slot: MealSlot | None = Field(
        default=None,
        description="本次推荐对应的餐次；缺省按当前时间推断",
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
    """rules_v6 权重画像：保留旧聚合键兼容旧客户端，新增明细键。

    旧聚合键值更新为 v6 子项之和（nutrition=12, seasonal_wellness=solar16+weather4=20,
    personal_family=constitution14+mood5+activity3+zodiac2=24, preference_history=15,
    feasibility=14, diversity=7）。明细键直接暴露 v6 九个基础分项与两项重排分。
    """

    nutrition: int = 12
    seasonal_wellness: int = 20
    personal_family: int = 24
    preference_history: int = 15
    feasibility: int = 14
    diversity: int = 7
    weather_modifier_limit: int = 4
    solar_term: int = 16
    weather: int = 4
    constitution: int = 14
    mood: int = 5
    activity: int = 3
    zodiac: int = 2
    exploration: int = 8


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

    meal_slot: MealSlot | None = Field(
        default=None,
        description="旧版单菜选择的目标餐次；缺省按当前时间推断",
    )

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


class ManualDish(BaseModel):
    """自记记录里的一道菜。"""

    name: str = Field(min_length=1, max_length=40)
    kcal: float | None = Field(default=None, ge=0, le=3000)


class DailyLogRead(BaseModel):
    """DailyLog 对外暴露的读模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    log_date: str
    meal_slot: str = "dinner"
    source: LogSource = "recommendation"
    shop_name: str | None = None
    note: str | None = None
    recommended_food_ids: list[int]
    chosen_food_ids: list[int]
    recommendation_id: int | None = None
    recommended_meal: MealSnapshot | None = None
    chosen_meal: MealSnapshot | None = None
    # source='manual' 时的菜品列表（宽松结构，不走 MealSnapshot）
    manual_dishes: list[ManualDish] | None = None
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
    streak_days: int = 0


class ManualLogRequest(BaseModel):
    """POST /daily/logs/manual 请求体（前端确认后的结构化数据直接落库）。"""

    log_date: str = Field(min_length=10, max_length=10, description="记录日期 ISO 格式")
    meal_slot: MealSlot
    dishes: list[ManualDish] = Field(default_factory=list, max_length=8)
    shop_name: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_content(self) -> "ManualLogRequest":
        if not self.dishes and not (self.note or "").strip():
            raise ValueError("至少记录一道菜或填写备注")
        return self


class UpdateLogRequest(BaseModel):
    """PATCH /daily/logs/{id} 请求体。

    recommendation 来源仅允许改 meal_slot/note（快照不可改）；
    manual 来源全字段可改。
    """

    meal_slot: MealSlot | None = None
    note: str | None = Field(default=None, max_length=500)
    dishes: list[ManualDish] | None = Field(default=None, max_length=8)
    shop_name: str | None = Field(default=None, max_length=80)


class FavoriteToggleResponse(BaseModel):
    """POST/DELETE /favorite/{food_id} 响应 data。"""

    food_id: int
    favorited: bool
