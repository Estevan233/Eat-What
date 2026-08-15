"""Non-destructive Food seed upsert service."""

import json
import os
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.food import Food


def resolve_seed_path(filename: str, *, module_file: Path | str = __file__) -> Path:
    """Resolve seed data outside site-packages when running an installed CLI."""
    runtime_data_dir = os.getenv("EAT_WHAT_DATA_DIR")
    if runtime_data_dir:
        return Path(runtime_data_dir) / filename

    return Path(module_file).resolve().parent.parent.parent / "data" / filename


DEFAULT_SEED_PATH = resolve_seed_path("food_seed.json")


def import_seed(session: Session, json_path: Path | str = DEFAULT_SEED_PATH) -> int:
    """Upsert seed rows by name and never delete production-created foods."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f'seed 文件不存在: {path}')

    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError(f'seed 文件顶层应是 list，实际是 {type(data).__name__}')

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
