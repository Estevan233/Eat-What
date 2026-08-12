import hashlib
import json

from sqlmodel import select

from app.models.food import Food
from app.services.food_seed import DEFAULT_SEED_PATH, import_seed
from app.services.recipe_seed import DEFAULT_RECIPE_SEED_PATH, import_recipe_seed
from scripts.validate_recipe_seed import validate

ORIGINAL_NAMES_SHA256 = '73cf37af0628f0deef3d175d6f42ccd2ccae6e13413a9fa325b92b7b7afb3e9b'


def _load_recipes() -> list[dict[str, object]]:
    return json.loads(DEFAULT_RECIPE_SEED_PATH.read_text(encoding='utf-8'))


def test_recipe_seed_quality_shape() -> None:
    recipes = _load_recipes()

    assert len(recipes) == 60
    assert len({item['food_name'] for item in recipes}) == 60
    assert sum(item['meal_role'] == 'main' for item in recipes) >= 20
    assert sum(item['meal_role'] == 'vegetable' for item in recipes) >= 20
    assert sum(item['meal_role'] == 'staple' for item in recipes) >= 10
    for item in recipes:
        assert 4 <= len(item['steps']) <= 6
        assert item['nutrition_per_serving']['energy_kcal'] > 0
        assert item['nutrition_basis']


def test_recipe_seed_passes_strict_validator() -> None:
    recipes = _load_recipes()
    foods = json.loads(DEFAULT_SEED_PATH.read_text(encoding='utf-8'))

    assert validate(recipes, {item['name'] for item in foods}) == []


def test_food_seed_keeps_original_names_and_adds_approved_soup() -> None:
    foods = json.loads(DEFAULT_SEED_PATH.read_text(encoding='utf-8'))
    names = {item['name'] for item in foods}

    assert len(foods) == 205
    assert '冬瓜香菜汤' in names
    original_names = sorted(names - {'冬瓜香菜汤'})
    digest = hashlib.sha256('\n'.join(original_names).encode()).hexdigest()
    assert digest == ORIGINAL_NAMES_SHA256


def test_food_import_is_non_destructive(session) -> None:
    custom = Food(
        name='用户自建菜',
        category='other',
        nature='neutral',
        cooking_method='other',
    )
    session.add(custom)
    session.commit()

    import_seed(session)

    assert session.exec(select(Food).where(Food.name == '用户自建菜')).first() is not None


def test_recipe_import_is_idempotent(session) -> None:
    import_seed(session)

    first = import_recipe_seed(session)
    second = import_recipe_seed(session)

    assert first == second == 60
