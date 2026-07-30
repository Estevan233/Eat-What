"""食物库 seed 数据校验脚本 - PRD 质量要求的可执行版。

校验内容：
1. schema 完整性：每条必有 name/category/nature/cooking_method/calories_kcal_per_100g
2. 字段约束：nature/flavor/cooking_method/suitable_constitutions 值在枚举内
3. 质量阈值：
   - 条数 ≥ MIN_FOODS（默认 200，第1步用 30 跑通时设 --min 30）
   - ≥ 90% 有 suitable_constitutions（至少一个）
   - ≥ 80% 有完整 nutrition 四项
   - ≥ 50% 有 seasonal_solar_terms
4. name 唯一性

跑：
    python3 backend/scripts/validate_food_seed.py            # 默认要求 200 条
    python3 backend/scripts/validate_food_seed.py --min 30   # 第1步跑通时用
    python3 backend/scripts/validate_food_seed.py --path custom.json

退出码：0 = 全过，1 = 有错误，2 = 有警告但通过
"""
import argparse
import json
import sys
from pathlib import Path

# ---- 枚举（与 PRD schema + cooking_method 实际用到的枚举同步）----

NATURE_VALUES = {"cold", "cool", "neutral", "warm", "hot"}
FLAVOR_VALUES = {"sour", "bitter", "sweet", "spicy", "salty", "bland", "numbing"}
COOKING_METHOD_VALUES = {
    "steam", "boil", "stir_fry", "deep_fry", "cold", "soup", "congee", "stew", "other"
}
CONSTITUTION_VALUES = {
    "pinghe", "qixu", "yangxu", "yinxu", "tanshi",
    "shire", "xueyu", "qiyu", "tebing",
}
WEATHER_VALUES = {"cold", "hot", "rainy", "dry", "humid", "any"}
# 节气 24 个
SOLAR_TERM_VALUES = {
    "lichun", "yushui", "jingzhe", "chunfen", "qingming", "guyu",
    "lixia", "xiaoman", "mangzhong", "xiazhi", "xiaoshu", "dachu",
    "liqiu", "chushu", "bailu", "qiufen", "hanlu", "shuangjiang",
    "lidong", "xiaoxue", "daxue", "dongzhi", "xiaohan", "dahan",
}

REQUIRED_FIELDS = ("name", "category", "nature", "cooking_method", "calories_kcal_per_100g")
NUTRITION_KEYS = ("protein_g", "fat_g", "carb_g", "fiber_g")

# 质量阈值（PRD 要求）
THRESHOLD_HAS_CONSTITUTIONS = 0.90
THRESHOLD_HAS_FULL_NUTRITION = 0.80
THRESHOLD_HAS_SOLAR_TERMS = 0.50


def validate(data: list, min_foods: int) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)。errors 会阻断，warnings 仅提示。"""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, list):
        return [f"顶层应是 list，实际是 {type(data).__name__}"], []

    if len(data) < min_foods:
        errors.append(f"条数不足：{len(data)} < {min_foods}")

    names_seen: dict[str, int] = {}
    for idx, item in enumerate(data):
        prefix = f"[#{idx}] "
        if not isinstance(item, dict):
            errors.append(f"{prefix}不是 dict")
            continue

        # 1. 必填字段
        for f in REQUIRED_FIELDS:
            if f not in item or item[f] is None or item[f] == "":
                errors.append(f"{prefix}缺必填字段 {f}")

        name = item.get("name")
        if name:
            if name in names_seen:
                errors.append(f"{prefix}name 重复: {name}（首次出现在 #{names_seen[name]}）")
            else:
                names_seen[name] = idx

        # 2. 枚举约束
        nature = item.get("nature")
        if nature and nature not in NATURE_VALUES:
            errors.append(f"{prefix}nature 非法值: {nature}（应为 {NATURE_VALUES}）")

        cm = item.get("cooking_method")
        if cm and cm not in COOKING_METHOD_VALUES:
            errors.append(f"{prefix}cooking_method 非法值: {cm}（应为 {COOKING_METHOD_VALUES}）")

        flavors = item.get("flavor") or []
        if not isinstance(flavors, list):
            errors.append(f"{prefix}flavor 应为 list，实际 {type(flavors).__name__}")
        else:
            bad = [f for f in flavors if f not in FLAVOR_VALUES]
            if bad:
                errors.append(f"{prefix}flavor 非法值: {bad}")

        cons = item.get("suitable_constitutions") or []
        if not isinstance(cons, list):
            errors.append(f"{prefix}suitable_constitutions 应为 list")
        else:
            bad = [c for c in cons if c not in CONSTITUTION_VALUES]
            if bad:
                errors.append(f"{prefix}suitable_constitutions 非法值: {bad}")

        weathers = item.get("suitable_weathers") or []
        if not isinstance(weathers, list):
            errors.append(f"{prefix}suitable_weathers 应为 list")
        else:
            bad = [w for w in weathers if w not in WEATHER_VALUES]
            if bad:
                errors.append(f"{prefix}suitable_weathers 非法值: {bad}")

        solar = item.get("seasonal_solar_terms") or []
        if not isinstance(solar, list):
            errors.append(f"{prefix}seasonal_solar_terms 应为 list")
        elif solar:
            bad = [s for s in solar if s not in SOLAR_TERM_VALUES]
            if bad:
                errors.append(f"{prefix}seasonal_solar_terms 非法值: {bad}")

        # 3. nutrition 结构
        nut = item.get("nutrition")
        if nut is not None and not isinstance(nut, dict):
            errors.append(f"{prefix}nutrition 应为 dict")

        # 4. calories 类型
        cal = item.get("calories_kcal_per_100g")
        if cal is not None and not isinstance(cal, int | float):
            errors.append(f"{prefix}calories_kcal_per_100g 应为 number，实际 {type(cal).__name__}")

    # 质量阈值（不阻断 errors 之外的检查，但低于阈值报 warning）
    if not data:
        return errors, warnings
    n = len(data)
    has_cons = sum(1 for x in data if x.get("suitable_constitutions"))
    has_full_nut = sum(
        1 for x in data
        if isinstance(x.get("nutrition"), dict)
        and all(k in x["nutrition"] for k in NUTRITION_KEYS)
    )
    has_solar = sum(1 for x in data if x.get("seasonal_solar_terms"))

    pct_cons = has_cons / n
    pct_nut = has_full_nut / n
    pct_solar = has_solar / n

    print(f"  质量统计: 条数={n}")
    print(f"    suitable_constitutions: {has_cons}/{n} = {pct_cons:.0%} (need >= {THRESHOLD_HAS_CONSTITUTIONS:.0%})")
    print(f"    full nutrition: {has_full_nut}/{n} = {pct_nut:.0%} (need >= {THRESHOLD_HAS_FULL_NUTRITION:.0%})")
    print(f"    seasonal_solar_terms: {has_solar}/{n} = {pct_solar:.0%} (need >= {THRESHOLD_HAS_SOLAR_TERMS:.0%})")

    if pct_cons < THRESHOLD_HAS_CONSTITUTIONS:
        errors.append(f"suitable_constitutions 覆盖率 {pct_cons:.0%} < {THRESHOLD_HAS_CONSTITUTIONS:.0%}")
    if pct_nut < THRESHOLD_HAS_FULL_NUTRITION:
        errors.append(f"完整 nutrition 覆盖率 {pct_nut:.0%} < {THRESHOLD_HAS_FULL_NUTRITION:.0%}")
    if pct_solar < THRESHOLD_HAS_SOLAR_TERMS:
        warnings.append(f"seasonal_solar_terms 覆盖率 {pct_solar:.0%} < {THRESHOLD_HAS_SOLAR_TERMS:.0%} (warning)")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 food_seed.json 数据质量")
    parser.add_argument("--path", default="backend/data/food_seed.json", help="seed 文件路径")
    parser.add_argument("--min", type=int, default=200, help="最少条数（默认 200，第1步跑通时用 --min 30）")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent.parent / args.path
    if not path.exists():
        print(f"[ERR] 文件不存在: {path}")
        return 1

    print(f"=== 校验 {path} ===")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    errors, warnings = validate(data, min_foods=args.min)

    if errors:
        print(f"\n[FAIL] {len(errors)} 个错误：")
        for e in errors:
            print(f"  - {e}")
        return 1
    if warnings:
        print(f"\n[WARN] {len(warnings)} 个警告：")
        for w in warnings:
            print(f"  - {w}")
        print("\n[OK] 校验通过（有警告）")
        return 2

    print("\n[OK] 校验通过，无错误无警告")
    return 0


if __name__ == "__main__":
    sys.exit(main())
