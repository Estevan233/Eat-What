from dataclasses import replace

import pytest

from app.models.recipe import Recipe
from app.services.meal_builder import MealCandidate, build_meal, meal_role_targets
from app.services.recommendation_ranking import RankedCandidate, ScoreBreakdown
from tests.services.test_recommender import _make_food


def _candidate(
    food_id: int,
    role: str,
    energy: float,
    score: float,
    *,
    cooking_method: str | None = None,
) -> MealCandidate:
    food = _make_food(
        f'{role}-{food_id}',
        cooking_method=cooking_method or f'method-{food_id}',
    )
    food.id = food_id
    food.meal_role = role
    food.recipe_ready = True
    food.visual_key = f'{role}-{food_id}'
    ranked = RankedCandidate(
        food=food,
        base_score=score,
        breakdown=ScoreBreakdown(
            nutrition=0,
            constitution=0,
            solar_term=0,
            weather=0,
            preference=0,
            feasibility=0,
            mood=0,
            activity=0,
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


@pytest.mark.parametrize(
    ("audience", "party_size", "expected"),
    [
        ("personal", 1, ("main", "vegetable", "staple")),
        ("family", 2, ("main", "vegetable", "staple")),
        ("family", 3, ("main", "main", "vegetable", "staple")),
        ("family", 4, ("main", "main", "vegetable", "staple")),
        ("family", 5, ("main", "main", "vegetable", "vegetable", "staple")),
        ("family", 6, ("main", "main", "vegetable", "vegetable", "staple")),
        ("family", 7, ("main", "main", "main", "vegetable", "vegetable", "staple")),
        ("family", 8, ("main", "main", "main", "vegetable", "vegetable", "staple")),
    ],
)
def test_meal_role_targets_scale_with_party_size(
    audience: str,
    party_size: int,
    expected: tuple[str, ...],
) -> None:
    assert meal_role_targets(audience, party_size) == expected


def test_family_meal_supports_repeated_roles_with_distinct_foods() -> None:
    candidates = [
        _candidate(1, 'main', 300, 90),
        _candidate(2, 'main', 280, 80),
        _candidate(3, 'main', 260, 70),
        _candidate(4, 'vegetable', 100, 85),
        _candidate(5, 'vegetable', 120, 75),
        _candidate(6, 'staple', 250, 65),
    ]
    targets = meal_role_targets('family', 8)

    result = build_meal(candidates, role_targets=targets)

    assert [item.meal_role for item in result.primary_meal.items] == list(targets)
    assert len({item.food_id for item in result.primary_meal.items}) == 6
    assert result.substitutions == []


def test_rules_v6_tie_break_prefers_distance_before_id() -> None:
    """rules_v6 严格 tie-break：同 final 时先选更久未曝光者（distance 更大）。"""
    near = _candidate(1, 'main', 300, 90)
    far = _candidate(2, 'main', 300, 90)
    near = MealCandidate(
        ranked=replace(near.ranked, exposure_distance_days=2),
        recipe=near.recipe,
        reason=near.reason,
    )
    far = MealCandidate(
        ranked=replace(far.ranked, exposure_distance_days=10),
        recipe=far.recipe,
        reason=far.reason,
    )
    vegetable = _candidate(3, 'vegetable', 100, 85)
    staple = _candidate(4, 'staple', 250, 80)

    result = build_meal([near, far, vegetable, staple])

    assert result.primary_meal.items[0].food_id == 2


def test_rules_v6_first_slot_gives_equal_seven_diversity_points() -> None:
    """rules_v6：首槽所有候选统一得 diversity_bonus=7，不改变首位相关性。"""
    main_a = _candidate(1, 'main', 300, 90)
    main_b = _candidate(2, 'main', 300, 85)
    vegetable = _candidate(3, 'vegetable', 100, 85)
    staple = _candidate(4, 'staple', 250, 80)

    result = build_meal([main_a, main_b, vegetable, staple])

    # 高分 main_a 应居首；diversity 不改变首位
    assert result.primary_meal.items[0].food_id == 1
