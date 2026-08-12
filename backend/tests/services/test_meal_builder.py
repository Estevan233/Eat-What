from app.models.recipe import Recipe
from app.services.meal_builder import MealCandidate, build_meal
from app.services.recommendation_ranking import RankedCandidate, ScoreBreakdown
from tests.services.test_recommender import _make_food


def _candidate(food_id: int, role: str, energy: float, score: float) -> MealCandidate:
    food = _make_food(f'{role}-{food_id}')
    food.id = food_id
    food.meal_role = role
    food.recipe_ready = True
    food.visual_key = f'{role}-{food_id}'
    ranked = RankedCandidate(
        food=food,
        base_score=score,
        breakdown=ScoreBreakdown(
            weather=0,
            solar_term=0,
            mood=0,
            nutrition=0,
            constitution=0,
            activity=0,
            method_time=0,
            zodiac=0,
        ),
        reason_phrases={},
    )
    recipe = Recipe(
        food_id=food_id,
        servings=2,
        ingredients_json=[],
        steps_json=['一', '二', '三', '四'],
        prep_time_min=5,
        cook_time_min=10 + food_id,
        nutrition_per_serving_json={
            'energy_kcal': energy,
            'protein_g': 10,
            'fat_g': 5,
            'carb_g': 20,
        },
        nutrition_basis='测试估算',
    )
    return MealCandidate(ranked=ranked, recipe=recipe, reason='测试推荐理由')


def test_builds_three_role_meal_and_two_substitutions() -> None:
    candidates = [
        _candidate(1, 'main', 300, 70),
        _candidate(2, 'vegetable', 120, 65),
        _candidate(3, 'staple', 260, 60),
        _candidate(4, 'main', 280, 55),
        _candidate(5, 'vegetable', 130, 50),
    ]

    result = build_meal(candidates)

    assert [item.meal_role for item in result.primary_meal.items] == [
        'main', 'vegetable', 'staple'
    ]
    assert len({item.food_id for item in result.primary_meal.items}) == 3
    assert result.primary_meal.total_nutrition.energy_kcal == 680
    assert result.primary_meal.estimated_time_min == 15 + 13
    assert len(result.substitutions) == 2


def test_sparse_candidates_never_create_unsafe_substitution() -> None:
    candidates = [
        _candidate(1, 'main', 300, 70),
        _candidate(2, 'vegetable', 120, 65),
        _candidate(3, 'staple', 260, 60),
    ]

    result = build_meal(candidates)

    assert result.substitutions == []
    assert result.substitution_notice
