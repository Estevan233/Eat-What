"""External dining and private shop+dish memory contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.daily import ActivityLevel, Audience, Mood

DiningVerdict = Literal["liked", "neutral", "avoided"]


class DiningMemoryUpsert(BaseModel):
    shop_name: str = Field(min_length=1, max_length=80)
    dish_name: str = Field(min_length=1, max_length=80)
    verdict: DiningVerdict = "neutral"
    note: str | None = Field(default=None, max_length=500)

    @field_validator("shop_name", "dish_name")
    @classmethod
    def reject_blank_identity(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("店铺和菜品名称不能为空")
        return cleaned

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class DiningMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_name: str
    dish_name: str
    verdict: DiningVerdict
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class DiningMemoryList(BaseModel):
    items: list[DiningMemoryRead]
    page: int
    size: int
    total: int


class ExternalDiningRequest(BaseModel):
    mood: Mood = "neutral"
    activity_level: ActivityLevel = "normal"
    audience: Audience = "personal"
    party_size: int = Field(default=1, ge=1, le=8)
    city: str | None = Field(default=None, max_length=64)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    exclude_keys: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("city")
    @classmethod
    def normalize_city(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @field_validator("exclude_keys")
    @classmethod
    def normalize_exclude_keys(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            key = value.strip()
            if not key:
                raise ValueError("排除项 key 不能为空")
            if key not in cleaned:
                cleaned.append(key)
        return cleaned

    @model_validator(mode="after")
    def validate_party_size(self) -> "ExternalDiningRequest":
        if self.audience == "personal" and self.party_size != 1:
            raise ValueError("个人模式人数必须为 1")
        if self.audience == "family" and self.party_size < 2:
            raise ValueError("家庭模式人数必须为 2-8")
        return self


class ExternalDiningSuggestion(BaseModel):
    key: str
    shop_name: str | None = None
    dish_name: str
    category: str
    meal_format: str
    serving_style: Literal["individual", "shared"]
    energy_kcal_min_per_person: int
    energy_kcal_max_per_person: int
    search_keywords: list[str]
    order_tips: list[str]
    reason: str
    seasonal_note: str
    nutrition_note: str
    source: Literal["rules", "memory"]


class ExternalDiningResponse(BaseModel):
    audience: Audience
    party_size: int
    city_label: str
    suggestions: list[ExternalDiningSuggestion]
    rotation_restarted: bool = False
    disclaimer: str
