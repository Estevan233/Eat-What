"""推荐曝光事件：一次成功推荐对应一行。"""
from datetime import date, datetime

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
    mood: str = Field(default="neutral", max_length=16)
    activity_level: str = Field(default="normal", max_length=8)
    weather_tag: str | None = Field(default=None, max_length=16)
    engine: str = Field(default="rules_v2", max_length=32)
    created_at: datetime = Field(default_factory=datetime.utcnow)
