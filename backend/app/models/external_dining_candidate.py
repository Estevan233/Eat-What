"""Audited external dining direction stored in the candidate catalog."""

from datetime import datetime

from sqlalchemy import Column, Index, String, Text
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class ExternalDiningCandidate(SQLModel, table=True):
    """A stable, source-backed direction; never a live merchant inventory row."""

    __tablename__ = "external_dining_candidates"
    __table_args__ = (
        Index("ix_external_dining_candidates_openid", "_openid"),
        Index(
            "ix_external_dining_candidates_review_active",
            "review_status",
            "is_active",
        ),
        Index(
            "ix_external_dining_candidates_family",
            "meal_family",
            "sub_family",
        ),
        Index(
            "ix_external_dining_candidates_serving_style",
            "serving_style",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    # CloudBase SQL 表统一保留 `_openid`，即使本目录只由服务端读取。
    openid_scope: str = Field(
        default="",
        max_length=64,
        exclude=True,
        sa_column=Column(
            "_openid",
            String(length=64),
            nullable=False,
            default="",
            index=False,
        ),
    )
    catalog_key: str = Field(unique=True, index=True, max_length=96)
    legacy_key: str | None = Field(default=None, unique=True, index=True, max_length=64)
    dish_name: str = Field(max_length=96, index=True)
    aliases_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    category: str = Field(max_length=64)
    meal_family: str = Field(max_length=32)
    sub_family: str = Field(max_length=48)
    cuisine_region: str = Field(default="unknown", max_length=48)
    staple_type: str = Field(default="unknown", max_length=32)
    protein_types_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    serving_style: str = Field(max_length=16)
    meal_periods_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    delivery_fit: str = Field(default="unknown", max_length=24)
    price_band: str = Field(default="unknown", max_length=16)
    nature: str = Field(default="unknown", max_length=16)
    seasonal_solar_terms_json: list[str] = Field(
        default_factory=lambda: ["all_season"],
        sa_column=Column(JSON),
    )
    source_url: str = Field(max_length=512)
    source_type: str = Field(max_length=32)
    source_checked_at: datetime
    nutrition_source_url: str | None = Field(default=None, max_length=512)
    nutrition_basis: str | None = Field(default=None, max_length=512)
    review_status: str = Field(default="draft", max_length=24)
    reviewed_by: str | None = Field(default=None, max_length=64)
    reviewed_at: datetime | None = Field(default=None)
    review_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    is_active: bool = Field(default=True)
    catalog_version: int = Field(default=1, ge=1)
    taxonomy_version: int = Field(default=1, ge=1)
    forbidden_tags_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    energy_kcal_min_per_person: int | None = Field(default=None, ge=0)
    energy_kcal_max_per_person: int | None = Field(default=None, ge=0)
    nutrition_note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    order_tips_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    high_protein: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
