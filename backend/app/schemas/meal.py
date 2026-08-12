from typing import Literal

from pydantic import BaseModel

from app.schemas.recipe import NutritionPerServing
from app.schemas.today_context import TodayContext
from app.schemas.weather import WeatherData

MealRole = Literal['main', 'vegetable', 'staple']


class MealItem(BaseModel):
    food_id: int
    name: str
    meal_role: MealRole
    category: str
    cooking_method: str
    visual_key: str
    prep_time_min: int
    cook_time_min: int
    nutrition_per_serving: NutritionPerServing
    reason: str
    score: float


class MealNutrition(BaseModel):
    energy_kcal: float
    protein_g: float
    fat_g: float
    carb_g: float


class MealSnapshot(BaseModel):
    items: list[MealItem]
    total_nutrition: MealNutrition
    estimated_time_min: int
    reason: str


class MealSubstitution(BaseModel):
    target_role: MealRole
    replacement: MealItem
    resulting_total: MealNutrition
    reason: str


class MealBuildResult(BaseModel):
    primary_meal: MealSnapshot
    substitutions: list[MealSubstitution]
    substitution_notice: str | None = None


class MealContext(BaseModel):
    weather: WeatherData
    today: TodayContext


class MealRecommendation(MealBuildResult):
    recommendation_id: int
    context: MealContext
    engine: str
