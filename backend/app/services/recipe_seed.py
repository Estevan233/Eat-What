"""Idempotent Recipe seed upsert service."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.food import Food
from app.models.recipe import Recipe
from app.repositories.cloudbase_rdb import RdbFilter
from app.repositories.cloudbase_repository import DatabaseSession, is_cloudbase_repository
from app.services.food_seed import resolve_seed_path

DEFAULT_RECIPE_SEED_PATH = resolve_seed_path("recipe_seed.json", module_file=__file__)


def _load_foods(session: DatabaseSession) -> dict[str, Food]:
    if is_cloudbase_repository(session):
        return {food.name: food for food in session.list(Food, limit=1000)}
    return {food.name: food for food in session.exec(select(Food)).all()}


def _load_recipes(session: DatabaseSession) -> dict[int, Recipe]:
    if is_cloudbase_repository(session):
        return {recipe.food_id: recipe for recipe in session.list(Recipe, limit=1000)}
    return {recipe.food_id: recipe for recipe in session.exec(select(Recipe)).all()}


def _insert_cloudbase_recipe(
    session: DatabaseSession,
    recipe: Recipe,
) -> Recipe:
    """Insert a recipe and recover rows when REST omits representation.

    CloudBase can acknowledge a successful insert with an empty response for
    tables containing JSON columns, even when ``Prefer: return=representation``
    is sent.  The write is still committed, so re-read by the unique
    ``food_id`` key before treating it as a failure.
    """
    if not is_cloudbase_repository(session):
        raise TypeError("_insert_cloudbase_recipe requires CloudBaseRepository")
    try:
        return session.insert(recipe)
    except RuntimeError as error:
        if "no representation" not in str(error) or recipe.food_id is None:
            raise
        recovered = session.first(
            Recipe,
            filters=(RdbFilter("food_id", "eq", recipe.food_id),),
        )
        if recovered is None:
            raise RuntimeError(
                "CloudBase REST recipe insert returned no representation and row was not found",
            ) from error
        return recovered


def _save_cloudbase_recipe_and_food(
    session: DatabaseSession,
    recipe: Recipe,
    food: Food,
) -> None:
    if not is_cloudbase_repository(session):
        return
    if recipe.id is None or food.id is None:
        raise RuntimeError(f"CloudBase recipe/food row missing id: {food.name}")
    _update_cloudbase_record(
        session,
        recipe,
        filters=(RdbFilter("id", "eq", recipe.id),),
    )
    _update_cloudbase_record(
        session,
        food,
        filters=(RdbFilter("id", "eq", food.id),),
    )


def _update_cloudbase_record(
    session: DatabaseSession,
    record: Recipe | Food,
    *,
    filters: tuple[RdbFilter, ...],
) -> None:
    """Accept successful REST updates whose gateway body is empty.

    The row is re-read with the same key filter so a genuinely missing row
    still fails closed instead of silently masking a permission or transport
    problem.
    """
    if not is_cloudbase_repository(session):
        raise TypeError("_update_cloudbase_record requires CloudBaseRepository")
    try:
        session.update(record, filters=filters)
    except RuntimeError as error:
        if "no representation" not in str(error):
            raise
        if session.first(type(record), filters=filters) is None:
            raise RuntimeError(
                "CloudBase REST update returned no representation and row was not found",
            ) from error


def import_recipe_seed(
    session: DatabaseSession,
    json_path: Path | str = DEFAULT_RECIPE_SEED_PATH,
) -> int:
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f'recipe seed 文件不存在: {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('recipe seed 顶层必须是 list')

    foods = _load_foods(session)
    recipes = _load_recipes(session)
    for item in data:
        food = foods.get(item['food_name'])
        if food is None or food.id is None:
            raise ValueError(f"菜谱对应食物不存在: {item['food_name']}")

        recipe = recipes.get(food.id)
        if recipe is None:
            recipe = Recipe(food_id=food.id, nutrition_basis=item['nutrition_basis'])
            if is_cloudbase_repository(session):
                recipe = _insert_cloudbase_recipe(session, recipe)
            else:
                session.add(recipe)
            recipes[food.id] = recipe

        _apply_recipe_item(recipe, item)
        food.meal_role = item['meal_role']
        food.visual_key = item['visual_key']
        food.recipe_ready = True
        _save_cloudbase_recipe_and_food(session, recipe, food)

    if isinstance(session, Session):
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
