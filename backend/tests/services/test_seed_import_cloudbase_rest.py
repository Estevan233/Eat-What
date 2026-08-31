"""CloudBase REST-shaped seed import regression tests."""

from __future__ import annotations

import json

from app.repositories.cloudbase_repository import CloudBaseRepository
from app.services import food_seed, recipe_seed
from tests.test_cloudbase_rest_services import MemoryRdbClient


def test_food_seed_upserts_through_cloudbase_repository(session, tmp_path) -> None:
    del session
    client = MemoryRdbClient()
    repository = CloudBaseRepository(client)
    seed_path = tmp_path / "foods.json"
    seed_path.write_text(
        json.dumps(
            [
                {
                    "name": "REST 测试饭",
                    "category": "staple",
                    "ingredients": ["大米"],
                    "nature": "neutral",
                    "cooking_method": "boil",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert food_seed.import_seed(repository, seed_path) == 1
    assert food_seed.import_seed(repository, seed_path) == 1
    rows = repository.list(food_seed.Food, limit=10)
    assert len(rows) == 1
    assert rows[0].catalog_key is not None
    assert rows[0].name == "REST 测试饭"


def test_recipe_seed_upserts_food_and_recipe_through_cloudbase_repository(tmp_path) -> None:
    client = MemoryRdbClient()
    repository = CloudBaseRepository(client)
    food_path = tmp_path / "foods.json"
    food_path.write_text(
        json.dumps(
            [
                {
                    "name": "REST 测试菜",
                    "category": "stir_fry",
                    "ingredients": ["鸡蛋"],
                    "nature": "neutral",
                    "cooking_method": "stir_fry",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    food_seed.import_seed(repository, food_path)
    recipe_path = tmp_path / "recipes.json"
    recipe_path.write_text(
        json.dumps(
            [
                {
                    "food_name": "REST 测试菜",
                    "meal_role": "main",
                    "visual_key": "rest-test",
                    "servings": 1,
                    "ingredients": [{"name": "鸡蛋", "amount": 2, "unit": "个"}],
                    "steps": ["打散鸡蛋", "加热锅具", "炒熟鸡蛋", "装盘"],
                    "prep_time_min": 5,
                    "cook_time_min": 5,
                    "nutrition_per_serving": {
                        "energy_kcal": 200,
                        "protein_g": 12,
                        "fat_g": 10,
                        "carb_g": 4,
                    },
                    "difficulty": "easy",
                    "nutrition_basis": "每份估算",
                    "version": 1,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert recipe_seed.import_recipe_seed(repository, recipe_path) == 1
    assert recipe_seed.import_recipe_seed(repository, recipe_path) == 1
    recipes = repository.list(recipe_seed.Recipe, limit=10)
    foods = repository.list(recipe_seed.Food, limit=10)
    assert len(recipes) == 1
    assert len(foods) == 1
    assert foods[0].recipe_ready is True
