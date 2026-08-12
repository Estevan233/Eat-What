"""Validate the fixed 60-recipe MVP dataset."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RECIPE_PATH = Path(__file__).resolve().parent.parent / 'data' / 'recipe_seed.json'
FOOD_PATH = Path(__file__).resolve().parent.parent / 'data' / 'food_seed.json'
ROLES = {'main', 'vegetable', 'staple'}
NUTRITION_KEYS = {'energy_kcal', 'protein_g', 'fat_g', 'carb_g'}


def validate(recipes: Any, food_names: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(recipes, list):
        return ['顶层必须是 list']
    if len(recipes) != 60:
        errors.append(f'菜谱必须恰好 60 条，实际 {len(recipes)} 条')

    names: set[str] = set()
    role_counts = {role: 0 for role in ROLES}
    for index, item in enumerate(recipes):
        prefix = f'[#{index}]'
        if not isinstance(item, dict):
            errors.append(f'{prefix} 必须是 object')
            continue
        name = item.get('food_name')
        if not isinstance(name, str) or not name:
            errors.append(f'{prefix} food_name 缺失')
        elif name in names:
            errors.append(f'{prefix} food_name 重复: {name}')
        else:
            names.add(name)
            if name not in food_names:
                errors.append(f'{prefix} food 不存在: {name}')

        role = item.get('meal_role')
        if role not in ROLES:
            errors.append(f'{prefix} meal_role 非法: {role}')
        else:
            role_counts[role] += 1

        steps = item.get('steps')
        if not isinstance(steps, list) or not 4 <= len(steps) <= 6:
            errors.append(f'{prefix} steps 必须为 4-6 步')
        elif any(not isinstance(step, str) or not step.strip() for step in steps):
            errors.append(f'{prefix} steps 含空步骤')

        nutrition = item.get('nutrition_per_serving')
        if not isinstance(nutrition, dict) or not NUTRITION_KEYS.issubset(nutrition):
            errors.append(f'{prefix} nutrition_per_serving 不完整')
        else:
            for key in NUTRITION_KEYS:
                value = nutrition[key]
                if not isinstance(value, int | float) or value < 0:
                    errors.append(f'{prefix} {key} 必须为非负数字')
            if nutrition.get('energy_kcal', 0) <= 0:
                errors.append(f'{prefix} energy_kcal 必须大于 0')

        ingredients = item.get('ingredients')
        if not isinstance(ingredients, list) or not ingredients:
            errors.append(f'{prefix} ingredients 缺失')
        else:
            for ingredient in ingredients:
                if not isinstance(ingredient, dict):
                    errors.append(f'{prefix} ingredient 必须是 object')
                    continue
                if not ingredient.get('name') or not ingredient.get('unit'):
                    errors.append(f'{prefix} ingredient 缺 name/unit')
                amount = ingredient.get('amount')
                if amount is None and not ingredient.get('optional'):
                    errors.append(f'{prefix} 非可选食材必须量化: {ingredient.get("name")}')
                if amount is not None and (not isinstance(amount, int | float) or amount <= 0):
                    errors.append(f'{prefix} 食材数量必须大于 0: {ingredient.get("name")}')

        source = item.get('source_url')
        if source is not None and (not isinstance(source, str) or not source.startswith('https://')):
            errors.append(f'{prefix} source_url 必须为 HTTPS')
        if not item.get('nutrition_basis'):
            errors.append(f'{prefix} nutrition_basis 缺失')

    for role, minimum in {'main': 20, 'vegetable': 20, 'staple': 10}.items():
        if role_counts[role] < minimum:
            errors.append(f'{role} 数量不足: {role_counts[role]} < {minimum}')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', type=Path, default=RECIPE_PATH)
    parser.add_argument('--food-path', type=Path, default=FOOD_PATH)
    args = parser.parse_args()
    recipes = json.loads(args.path.read_text(encoding='utf-8'))
    foods = json.loads(args.food_path.read_text(encoding='utf-8'))
    errors = validate(recipes, {item['name'] for item in foods})
    if errors:
        print(f'[FAIL] {len(errors)} 个错误')
        for message in errors:
            print(f'  - {message}')
        return 1
    print('[OK] 60 条菜谱通过结构、角色、营养、量化食材与来源校验')
    return 0


if __name__ == '__main__':
    sys.exit(main())
