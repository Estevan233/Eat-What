"""收藏表 - 用户收藏的食物。

学习点：
- 普通收藏：(user_id, food_id) 联合唯一；自定义收藏：(user_id, custom_name) 联合唯一
- food_id 可空：自定义收藏不依赖候选库（如外食吃到的菜、自己常做的菜）
- MySQL 唯一约束对 NULL 不生效，普通收藏行（food_id 非空）与自定义行互不干扰
- 外键指向 users / foods，级联删除跟随用户/菜被删
"""
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Favorite(SQLModel, table=True):
    """用户收藏的一条记录（普通收藏或自定义收藏）。"""

    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "food_id", name="uq_favorites_user_food"),
        UniqueConstraint("user_id", "custom_name", name="uq_favorites_user_custom"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    # 普通收藏关联的候选菜品；自定义收藏为 NULL
    food_id: int | None = Field(default=None, foreign_key="foods.id", index=True)
    # 自定义收藏名称（如"楼下小王的番茄鸡蛋盖饭"）
    custom_name: str | None = Field(default=None, max_length=80)
    # 备注（做法要点、店铺来源、个人喜好等）
    note: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)
