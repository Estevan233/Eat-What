"""Non-destructive Food seed upsert service."""

import json
import os
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from sqlmodel import select

from app.models.food import Food
from app.repositories.cloudbase_rdb import RdbFilter
from app.repositories.cloudbase_repository import DatabaseSession, is_cloudbase_repository


def resolve_seed_path(filename: str, *, module_file: Path | str = __file__) -> Path:
    """Resolve seed data outside site-packages when running an installed CLI."""
    runtime_data_dir = os.getenv("EAT_WHAT_DATA_DIR")
    if runtime_data_dir:
        return Path(runtime_data_dir) / filename

    return Path(module_file).resolve().parent.parent.parent / "data" / filename


DEFAULT_SEED_PATH = resolve_seed_path("food_seed.json")


def _catalog_key(name: str) -> str:
    digest = sha256(name.encode("utf-8")).hexdigest()[:16]
    return f"home:food-{digest}:v1"


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError("source_checked_at/reviewed_at 必须是 ISO 日期时间")


def _apply_catalog_scalars(record: Food, item: dict[str, Any]) -> None:
    record.catalog_key = item.get("catalog_key") or record.catalog_key or _catalog_key(item["name"])
    if "aliases" in item:
        record.aliases_json = list(item.get("aliases", []))
    for field, source in (
        ("meal_family", "meal_family"),
        ("sub_family", "sub_family"),
        ("cuisine_region", "cuisine_region"),
        ("staple_type", "staple_type"),
        ("serving_style", "serving_style"),
        ("delivery_fit", "delivery_fit"),
        ("price_band", "price_band"),
        ("source_url", "source_url"),
        ("source_type", "source_type"),
        ("review_status", "review_status"),
        ("reviewed_by", "reviewed_by"),
        ("review_notes", "review_notes"),
        ("nutrition_source_url", "nutrition_source_url"),
        ("nutrition_basis", "nutrition_basis"),
    ):
        if source in item:
            setattr(record, field, item[source])


def _apply_catalog_lists_and_dates(record: Food, item: dict[str, Any]) -> None:
    if "protein_types" in item:
        record.protein_types_json = list(item.get("protein_types", []))
    if "meal_periods" in item:
        record.meal_periods_json = list(item.get("meal_periods", []))
    if "source_checked_at" in item:
        record.source_checked_at = _parse_datetime(item.get("source_checked_at"))
    if "reviewed_at" in item:
        record.reviewed_at = _parse_datetime(item.get("reviewed_at"))
    if "is_active" in item:
        record.is_active = bool(item["is_active"])
    if "catalog_version" in item:
        record.catalog_version = int(item["catalog_version"])
    if "taxonomy_version" in item:
        record.taxonomy_version = int(item["taxonomy_version"])


def _apply_catalog_fields(record: Food, item: dict[str, Any]) -> None:
    _apply_catalog_scalars(record, item)
    _apply_catalog_lists_and_dates(record, item)


def import_seed(session: DatabaseSession, json_path: Path | str = DEFAULT_SEED_PATH) -> int:
    """Upsert seed rows by name and never delete production-created foods."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f'seed 文件不存在: {path}')

    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError(f'seed 文件顶层应是 list，实际是 {type(data).__name__}')

    if is_cloudbase_repository(session):
        existing_rows = session.list(Food, limit=1000)
        existing_by_key = {
            food.catalog_key: food
            for food in existing_rows
            if food.catalog_key
        }
        existing_by_name = {food.name: food for food in existing_rows}
        for item in data:
            name = str(item["name"])
            key = str(item.get("catalog_key") or _catalog_key(name))
            record = existing_by_key.get(key) or existing_by_name.get(name)
            if record is None:
                record = _build_food_record(item)
                record.catalog_key = key
                record = session.insert(record)
            else:
                _apply_food_item(record, item)
                if record.id is None:
                    raise RuntimeError(f"CloudBase foods row missing id: {name}")
                record = session.update(
                    record,
                    filters=(RdbFilter("id", "eq", record.id),),
                )
            existing_by_key[key] = record
            existing_by_name[record.name] = record
        return len(data)

    existing_by_name = {food.name: food for food in session.exec(select(Food)).all()}
    for item in data:
        record = existing_by_name.get(item['name'])
        if record is None:
            record = _build_food_record(item)
            session.add(record)
            existing_by_name[record.name] = record
        else:
            _apply_food_item(record, item)

    session.commit()
    return len(data)


def _apply_food_item(record: Food, item: dict[str, Any]) -> None:
    _apply_catalog_fields(record, item)
    record.category = item.get('category', 'other')
    record.ingredients_json = list(item.get('ingredients', []))
    record.calories_kcal_per_100g = item.get('calories_kcal_per_100g')
    record.nutrition_json = dict(item.get('nutrition', {}) or {})
    record.nature = item.get('nature', 'neutral')
    record.flavor_json = list(item.get('flavor', []))
    record.organ_meridians_json = list(item.get('organ_meridians', []))
    record.suitable_constitutions_json = list(item.get('suitable_constitutions', []))
    record.suitable_weathers_json = list(item.get('suitable_weathers', ['any']))
    record.forbidden_for_json = list(item.get('forbidden_for', []))
    record.tags_json = list(item.get('tags', []))
    record.cooking_method = item.get('cooking_method', 'other')
    record.cooking_time_min = item.get('cooking_time_min')
    record.image_url = item.get('image_url')
    record.seasonal_solar_terms_json = list(item.get('seasonal_solar_terms', []))
    record.description = item.get('description')
    if 'meal_role' in item:
        record.meal_role = item.get('meal_role')
    if 'recipe_ready' in item:
        record.recipe_ready = bool(item.get('recipe_ready'))
    if 'visual_key' in item:
        record.visual_key = item.get('visual_key')


def _build_food_record(item: dict[str, Any]) -> Food:
    record = Food(
        name=item['name'],
        category=item.get('category', 'other'),
        nature=item.get('nature', 'neutral'),
        cooking_method=item.get('cooking_method', 'other'),
    )
    _apply_food_item(record, item)
    return record
