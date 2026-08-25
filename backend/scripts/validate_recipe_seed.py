"""Validate the production 120-recipe dataset before import."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RECIPE_PATH = Path(__file__).resolve().parent.parent / 'data' / 'recipe_seed.json'
FOOD_PATH = Path(__file__).resolve().parent.parent / 'data' / 'food_seed.json'
ROLES = {'main', 'vegetable', 'staple'}
NUTRITION_KEYS = {'energy_kcal', 'protein_g', 'fat_g', 'carb_g'}
EXPECTED_ROLE_COUNTS = {'main': 50, 'vegetable': 50, 'staple': 20}
OPTIONAL_CONDIMENTS = {
    '盐', '白胡椒粉', '黑胡椒粉', '胡椒粉', '香油', '醋', '葱花', '香菜',
}
ANIMAL_FOOD_MARKERS = {
    '肉', '排骨', '猪', '牛', '羊', '鸡', '鸭', '鹅', '蛋', '鱼', '虾', '蟹', '贝',
    '蛤', '鱿鱼', '里脊', '肝', '腩', '翅',
}
DONENESS_MARKERS = {
    '熟透', '全熟', '煮熟', '蒸熟', '炒熟', '炖熟', '煎熟', '烤熟', '凝固',
    '无血色', '中心熟', '变色且熟', '肉汁清澈',
}
FORBIDDEN_CLAIMS = {
    '治疗', '治愈', '根治', '保证减脂', '包瘦', '降血压', '降血糖', '排毒',
}
SMALL_INGREDIENT_MAX_G = {
    '紫菜': 20,
    '虾皮': 30,
    '花生': 80,
    '腰果': 100,
    '松仁': 80,
    '干辣椒': 50,
    '花椒': 20,
    '八角': 20,
    '桂皮': 20,
    '香叶': 20,
    '盐': 15,
    '枸杞': 30,
    '桂圆': 50,
    '红枣': 80,
}


def validate(recipes: Any, food_names: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(recipes, list):
        return ['顶层必须是 list']
    if len(recipes) != 120:
        errors.append(f'菜谱必须恰好 120 条，实际 {len(recipes)} 条')

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
        joined_steps = ''.join(steps) if isinstance(steps, list) else ''

        nutrition = item.get('nutrition_per_serving')
        if not isinstance(nutrition, dict) or not NUTRITION_KEYS.issubset(nutrition):
            errors.append(f'{prefix} nutrition_per_serving 不完整')
        else:
            for key in NUTRITION_KEYS:
                value = nutrition[key]
                if not isinstance(value, int | float) or value <= 0:
                    errors.append(f'{prefix} {key} 必须为正数')
            bounds = {'energy_kcal': 1200, 'protein_g': 120, 'fat_g': 100, 'carb_g': 200}
            for key, upper in bounds.items():
                value = nutrition.get(key)
                if isinstance(value, int | float) and value > upper:
                    errors.append(f'{prefix} {key} 超出每份合理上界 {upper}')

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
                ingredient_name = ingredient.get('name')
                upper = SMALL_INGREDIENT_MAX_G.get(str(ingredient_name))
                if (
                    upper is not None
                    and ingredient.get('unit') == 'g'
                    and isinstance(amount, int | float)
                    and amount > upper
                ):
                    errors.append(f'{prefix} {ingredient_name} 用量异常: {amount}g > {upper}g')
                if (
                    amount is None
                    and isinstance(ingredient_name, str)
                    and ingredient_name not in OPTIONAL_CONDIMENTS
                ):
                    errors.append(f'{prefix} 只有调味料可不定量: {ingredient_name}')
                if (
                    isinstance(ingredient_name, str)
                    and not ingredient.get('optional')
                    and ingredient_name not in joined_steps
                ):
                    errors.append(f'{prefix} 步骤未覆盖关键食材: {ingredient_name}')

            ingredient_text = ''.join(
                str(ingredient.get('name', ''))
                for ingredient in ingredients
                if isinstance(ingredient, dict)
            )
            if any(marker in ingredient_text for marker in ANIMAL_FOOD_MARKERS) and not any(
                marker in joined_steps for marker in DONENESS_MARKERS
            ):
                errors.append(f'{prefix} 肉蛋水产缺少明确熟制提示')

        for key, lower, upper in (
            ('servings', 1, 8),
            ('prep_time_min', 0, 120),
            ('cook_time_min', 1, 240),
            ('version', 1, 99),
        ):
            value = item.get(key)
            if not isinstance(value, int) or not lower <= value <= upper:
                errors.append(f'{prefix} {key} 必须为 {lower}-{upper} 的整数')
        if item.get('difficulty') not in {'easy', 'medium', 'hard'}:
            errors.append(f'{prefix} difficulty 非法')

        source = item.get('source_url')
        if source is not None and (not isinstance(source, str) or not source.startswith('https://')):
            errors.append(f'{prefix} source_url 必须为 HTTPS')
        nutrition_basis = item.get('nutrition_basis')
        if not isinstance(nutrition_basis, str) or '每份' not in nutrition_basis:
            errors.append(f'{prefix} nutrition_basis 缺失')
        searchable_text = joined_steps + str(nutrition_basis or '')
        for claim in FORBIDDEN_CLAIMS:
            if claim in searchable_text:
                errors.append(f'{prefix} 含不允许的疗效承诺: {claim}')

    for role, expected in EXPECTED_ROLE_COUNTS.items():
        if role_counts[role] != expected:
            errors.append(f'{role} 数量必须为 {expected}，实际 {role_counts[role]}')
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
    print('[OK] 120 条菜谱通过结构、角色、营养、熟制、量化食材与来源校验')
    return 0


if __name__ == '__main__':
    sys.exit(main())
