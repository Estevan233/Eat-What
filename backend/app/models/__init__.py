"""数据模型聚合 - 在这里 import 所有表，让 init_db() 知道要建哪些。"""
from app.models.user import User
from app.models.user_profile import UserProfile

__all__ = ["User", "UserProfile"]
