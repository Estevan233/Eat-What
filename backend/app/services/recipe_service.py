from sqlmodel import select

from app.models.food import Food
from app.models.recipe import Recipe
from app.repositories.cloudbase_rdb import RdbFilter
from app.repositories.cloudbase_repository import DatabaseSession, is_cloudbase_repository
from app.schemas.recipe import RecipeRead


def get_by_food_id(session: DatabaseSession, food_id: int) -> RecipeRead | None:
    if is_cloudbase_repository(session):
        recipe = session.first(
            Recipe,
            filters=(RdbFilter('food_id', 'eq', food_id),),
        )
    else:
        recipe = session.exec(select(Recipe).where(Recipe.food_id == food_id)).first()
    if recipe is None:
        return None
    food = session.get(Food, food_id)
    if food is None:
        return None
    return RecipeRead(
        food_id=food_id,
        food_name=food.name,
        meal_role=food.meal_role or 'main',
        visual_key=food.visual_key or 'meal-default',
        servings=recipe.servings,
        ingredients=recipe.ingredients_json,
        steps=recipe.steps_json,
        prep_time_min=recipe.prep_time_min,
        cook_time_min=recipe.cook_time_min,
        nutrition_per_serving=recipe.nutrition_per_serving_json,
        difficulty=recipe.difficulty,
        source_url=recipe.source_url,
        nutrition_basis=recipe.nutrition_basis,
        version=recipe.version,
    )
