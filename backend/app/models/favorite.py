"""收藏表 - 用户收藏的食物。

学习点：
- (user_id, food_id) 联合唯一：同一道菜只能收藏一次
- 用 unique constraint 而非应用层判断，DB 层兜底防重
- 外键指向 users / foods，级联删除跟随用户/菜被删
"""
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Favorite(SQLModel, table=True):
    """用户收藏的一条记录。"""

    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "food_id", name="uq_favorites_user_food"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    food_id: int = Field(foreign_key="foods.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
