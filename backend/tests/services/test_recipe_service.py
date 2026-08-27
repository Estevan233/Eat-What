from app.services import food_service, recipe_service
from app.services.food_seed import import_seed
from app.services.recipe_seed import import_recipe_seed


def test_get_recipe_by_food_id(session) -> None:
    import_seed(session)
    import_recipe_seed(session)
    food = food_service.get_by_name(session, '冬瓜香菜汤')
    assert food is not None and food.id is not None

    recipe = recipe_service.get_by_food_id(session, food.id)

    assert recipe is not None
    assert recipe.food_name == '冬瓜香菜汤'
    assert recipe.meal_role == 'vegetable'
    assert recipe.nutrition_per_serving.energy_kcal == 77
    assert recipe.version == 2
    assert len(recipe.steps) == 4
    assert recipe.ingredients[0].amount == 400


def test_get_recipe_returns_none_for_missing_food(session) -> None:
    assert recipe_service.get_by_food_id(session, 999_999) is None
