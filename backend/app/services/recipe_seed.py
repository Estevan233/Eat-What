"""Idempotent Recipe seed upsert service."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.food import Food
from app.models.recipe import Recipe
from app.services.food_seed import resolve_seed_path

DEFAULT_RECIPE_SEED_PATH = resolve_seed_path("recipe_seed.json", module_file=__file__)


def import_recipe_seed(
    session: Session,
    json_path: Path | str = DEFAULT_RECIPE_SEED_PATH,
) -> int:
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f'recipe seed 文件不存在: {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('recipe seed 顶层必须是 list')

    foods = {food.name: food for food in session.exec(select(Food)).all()}
    recipes = {recipe.food_id: recipe for recipe in session.exec(select(Recipe)).all()}
    for item in data:
        food = foods.get(item['food_name'])
        if food is None or food.id is None:
            raise ValueError(f"菜谱对应食物不存在: {item['food_name']}")

        recipe = recipes.get(food.id)
        if recipe is None:
            recipe = Recipe(food_id=food.id, nutrition_basis=item['nutrition_basis'])
            session.add(recipe)
            recipes[food.id] = recipe

        _apply_recipe_item(recipe, item)
        food.meal_role = item['meal_role']
        food.visual_key = item['visual_key']
        food.recipe_ready = True

    session.commit()
    return len(data)


def _apply_recipe_item(recipe: Recipe, item: dict[str, Any]) -> None:
    recipe.servings = int(item['servings'])
    recipe.ingredients_json = list(item['ingredients'])
    recipe.steps_json = list(item['steps'])
    recipe.prep_time_min = int(item['prep_time_min'])
    recipe.cook_time_min = int(item['cook_time_min'])
    recipe.nutrition_per_serving_json = dict(item['nutrition_per_serving'])
    recipe.difficulty = item['difficulty']
    recipe.source_url = item.get('source_url')
    recipe.nutrition_basis = item['nutrition_basis']
    recipe.version = int(item.get('version', 1))
    recipe.updated_at = datetime.utcnow()
