from dataclasses import dataclass

from app.models.recipe import Recipe
from app.schemas.meal import (
    MealBuildResult,
    MealItem,
    MealNutrition,
    MealRole,
    MealSnapshot,
    MealSubstitution,
)
from app.schemas.recipe import NutritionPerServing
from app.services.recommendation_ranking import RankedCandidate


@dataclass(frozen=True)
class MealCandidate:
    ranked: RankedCandidate
    recipe: Recipe
    reason: str


def _nutrition(recipe: Recipe) -> NutritionPerServing:
    values = recipe.nutrition_per_serving_json
    return NutritionPerServing(
        energy_kcal=float(values.get('energy_kcal', 0)),
        protein_g=float(values.get('protein_g', 0)),
        fat_g=float(values.get('fat_g', 0)),
        carb_g=float(values.get('carb_g', 0)),
    )


def _to_item(candidate: MealCandidate) -> MealItem:
    food = candidate.ranked.food
    if food.id is None or food.meal_role not in {'main', 'vegetable', 'staple'}:
        raise ValueError('完整一餐候选缺少有效 food_id 或 meal_role')
    return MealItem(
        food_id=food.id,
        name=food.name,
        meal_role=food.meal_role,
        category=food.category,
        cooking_method=food.cooking_method,
        visual_key=food.visual_key or 'meal-default',
        prep_time_min=candidate.recipe.prep_time_min,
        cook_time_min=candidate.recipe.cook_time_min,
        nutrition_per_serving=_nutrition(candidate.recipe),
        reason=candidate.reason,
        score=candidate.ranked.normalized_score,
    )


def _sum_nutrition(items: list[MealItem]) -> MealNutrition:
    return MealNutrition(
        energy_kcal=round(sum(item.nutrition_per_serving.energy_kcal for item in items), 1),
        protein_g=round(sum(item.nutrition_per_serving.protein_g for item in items), 1),
        fat_g=round(sum(item.nutrition_per_serving.fat_g for item in items), 1),
        carb_g=round(sum(item.nutrition_per_serving.carb_g for item in items), 1),
    )


def _choose_primary(candidates: list[MealCandidate]) -> list[MealCandidate]:
    ordered = sorted(
        candidates,
        key=lambda candidate: (-candidate.ranked.final_raw_score, candidate.ranked.food.id or 0),
    )
    selected: list[MealCandidate] = []
    used_ids: set[int] = set()
    used_methods: set[str] = set()
    for role in ('main', 'vegetable', 'staple'):
        matching = [candidate for candidate in ordered if candidate.ranked.food.meal_role == role]
        if not matching:
            raise ValueError(f'安全候选不足，缺少 {role} 槽位')
        diverse = [
            candidate for candidate in matching
            if candidate.ranked.food.id not in used_ids
            and candidate.ranked.food.cooking_method not in used_methods
        ]
        chosen = (diverse or [c for c in matching if c.ranked.food.id not in used_ids])[0]
        selected.append(chosen)
        if chosen.ranked.food.id is not None:
            used_ids.add(chosen.ranked.food.id)
        used_methods.add(chosen.ranked.food.cooking_method)
    return selected


def _meal_snapshot(items: list[MealItem]) -> MealSnapshot:
    return MealSnapshot(
        items=items,
        total_nutrition=_sum_nutrition(items),
        estimated_time_min=(
            sum(item.prep_time_min for item in items)
            + max(item.cook_time_min for item in items)
        ),
        reason='主菜、蔬菜和主食各一份，兼顾营养与做法多样性。',
    )


def _substitution(
    primary: list[MealItem],
    replacement: MealItem,
    role: MealRole,
) -> MealSubstitution:
    resulting = [replacement if item.meal_role == role else item for item in primary]
    return MealSubstitution(
        target_role=role,
        replacement=replacement,
        resulting_total=_sum_nutrition(resulting),
        reason=f'可将{role}替换为{replacement.name}，能量仍接近主方案。',
    )


def build_meal(candidates: list[MealCandidate]) -> MealBuildResult:
    selected = _choose_primary(candidates)
    primary_items = [_to_item(candidate) for candidate in selected]
    primary_ids = {item.food_id for item in primary_items}
    substitutions: list[MealSubstitution] = []
    for role in ('main', 'vegetable'):
        current = next(item for item in primary_items if item.meal_role == role)
        alternatives = [
            _to_item(candidate)
            for candidate in sorted(
                candidates,
                key=lambda candidate: (-candidate.ranked.final_raw_score, candidate.ranked.food.id or 0),
            )
            if candidate.ranked.food.meal_role == role
            and candidate.ranked.food.id not in primary_ids
        ]
        for tolerance in (0.25, 0.35):
            replacement = next(
                (
                    item for item in alternatives
                    if abs(item.nutrition_per_serving.energy_kcal - current.nutrition_per_serving.energy_kcal)
                    <= current.nutrition_per_serving.energy_kcal * tolerance
                ),
                None,
            )
            if replacement is not None:
                substitutions.append(_substitution(primary_items, replacement, role))
                break

    notice = None
    if len(substitutions) < 2:
        notice = '当前符合忌口和体质条件的安全替换较少，未放宽硬性过滤。'
    return MealBuildResult(
        primary_meal=_meal_snapshot(primary_items),
        substitutions=substitutions,
        substitution_notice=notice,
    )
