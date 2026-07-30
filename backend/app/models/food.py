"""食物表 - 推荐算法的核心数据源。

学习点：
- JSON 列存 list/dict 结构（ingredients/nutrition/tags 等），MVP 不需反查
- name 唯一约束：seed-food 重复导入时按 name upsert，保证幂等
- 性味归经用英文枚举键存，UI 层再映射中文名，避免 DB 存中文
"""
from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class Food(SQLModel, table=True):
    """一道家常菜的结构化记录。"""

    __tablename__ = "foods"

    id: int | None = Field(default=None, primary_key=True)
    # name 唯一 + 索引：seed-food upsert 按 name，搜索也按 name
    name: str = Field(unique=True, index=True, max_length=64)
    category: str = Field(max_length=32, index=True)
    ingredients_json: list[str] = Field(default=[], sa_column=Column(JSON))
    # 可空：少数菜没有可靠营养数据，宁可少标不杜撰
    calories_kcal_per_100g: float | None = Field(default=None)
    nutrition_json: dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    # nature: cold | cool | neutral | warm | hot
    nature: str = Field(max_length=16, index=True)
    # flavor: subset of [sour, bitter, sweet, spicy, salty, bland]
    flavor_json: list[str] = Field(default=[], sa_column=Column(JSON))
    organ_meridians_json: list[str] = Field(default=[], sa_column=Column(JSON))
    suitable_constitutions_json: list[str] = Field(default=[], sa_column=Column(JSON))
    suitable_weathers_json: list[str] = Field(default=[], sa_column=Column(JSON))
    forbidden_for_json: list[str] = Field(default=[], sa_column=Column(JSON))
    tags_json: list[str] = Field(default=[], sa_column=Column(JSON))
    # cooking_method: steam | boil | stir_fry | deep_fry | cold | soup | congee | other
    cooking_method: str = Field(max_length=32, index=True)
    cooking_time_min: int | None = Field(default=None)
    image_url: str | None = Field(default=None, max_length=512)
    seasonal_solar_terms_json: list[str] = Field(default=[], sa_column=Column(JSON))
    description: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_read_dict(self) -> dict[str, Any]:
        """转成对外暴露的 dict（API 序列化用）。

        把 *_json 字段去掉后缀，让前端拿到的是 ingredients / flavor 等干净 key。
        """
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "ingredients": list(self.ingredients_json),
            "calories_kcal_per_100g": self.calories_kcal_per_100g,
            "nutrition": dict(self.nutrition_json) if self.nutrition_json else {},
            "nature": self.nature,
            "flavor": list(self.flavor_json),
            "organ_meridians": list(self.organ_meridians_json),
            "suitable_constitutions": list(self.suitable_constitutions_json),
            "suitable_weathers": list(self.suitable_weathers_json),
            "forbidden_for": list(self.forbidden_for_json),
            "tags": list(self.tags_json),
            "cooking_method": self.cooking_method,
            "cooking_time_min": self.cooking_time_min,
            "image_url": self.image_url,
            "seasonal_solar_terms": list(self.seasonal_solar_terms_json),
            "description": self.description,
        }
