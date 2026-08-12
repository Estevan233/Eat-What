"""Structured, versioned recipe attached one-to-one to a Food."""

from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class Recipe(SQLModel, table=True):
    __tablename__ = 'recipes'

    id: int | None = Field(default=None, primary_key=True)
    food_id: int = Field(foreign_key='foods.id', unique=True, index=True)
    servings: int = Field(default=2, ge=1)
    ingredients_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    steps_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    prep_time_min: int = Field(default=10, ge=0)
    cook_time_min: int = Field(default=15, ge=0)
    nutrition_per_serving_json: dict[str, float] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )
    difficulty: str = Field(default='easy', max_length=16)
    source_url: str | None = Field(default=None, max_length=512)
    nutrition_basis: str = Field(max_length=512)
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
