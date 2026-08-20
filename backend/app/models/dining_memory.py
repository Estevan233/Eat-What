"""Private user memory for one exact shop and dish pair."""

from datetime import datetime

from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class DiningMemory(SQLModel, table=True):
    __tablename__ = "dining_memories"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "normalized_shop_name",
            "normalized_dish_name",
            name="uq_dining_memories_user_shop_dish",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    shop_name: str = Field(max_length=80)
    dish_name: str = Field(max_length=80)
    normalized_shop_name: str = Field(max_length=80)
    normalized_dish_name: str = Field(max_length=80)
    verdict: str = Field(default="neutral", max_length=16, index=True)
    note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
