"""推荐曝光事件：一次成功推荐对应一行。"""
from datetime import date, datetime
from typing import Any

from sqlalchemy import Column, Index
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class RecommendationEvent(SQLModel, table=True):
    """记录一次推荐曝光，不保存位置和用户身体数据。"""

    __tablename__ = "recommendation_events"
    __table_args__ = (
        Index("ix_recommendation_events_user_date", "user_id", "event_date"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    event_date: date = Field(index=True)
    recommended_food_ids_json: list[int] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    primary_food_ids_json: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    substitution_options_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    primary_meal_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    mood: str = Field(default="neutral", max_length=16)
    activity_level: str = Field(default="normal", max_length=8)
    weather_tag: str | None = Field(default=None, max_length=16)
    dining_mode: str = Field(default="cook", max_length=16)
    audience: str = Field(default="personal", max_length=16)
    party_size: int = Field(default=1)
    engine: str = Field(default="rules_v2", max_length=32)
    scorer_version: str = Field(default="rules_v2", max_length=32)
    builder_version: str = Field(default="legacy", max_length=32)
    agent_name: str | None = Field(default=None, max_length=64)
    summary_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
