"""数据模型聚合 - 在这里 import 所有表，让 init_db() 知道要建哪些。"""
from app.models.daily_log import DailyLog
from app.models.dining_memory import DiningMemory
from app.models.favorite import Favorite
from app.models.food import Food
from app.models.recipe import Recipe
from app.models.recommendation_event import RecommendationEvent
from app.models.user import User
from app.models.user_profile import UserProfile

__all__ = [
    "DailyLog",
    "DiningMemory",
    "Favorite",
    "Food",
    "Recipe",
    "RecommendationEvent",
    "User",
    "UserProfile",
]
