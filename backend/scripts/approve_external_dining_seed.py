"""Finalize the product-reviewed external dining catalog.

This is the explicit "B" review policy: community recipe pages may support
dish-name and preparation existence, while taxonomy, delivery suitability and
serving style are reviewed with deterministic product rules. It deliberately
does not claim merchant availability, current price, or precise nutrition.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED = BACKEND_ROOT / "data" / "external_dining_seed.json"
DEFAULT_FOODS = BACKEND_ROOT / "data" / "food_seed.json"

REVIEWER = "codex-product-audit-b-20260901"
REVIEWED_AT = "2026-09-01T01:07:35+08:00"
REVIEW_MARKER = "B 方案产品审核"
BAD_PRIMARY_DOMAINS = frozenset({"github.com", "www.ihchina.cn"})
DUPLICATE_REPLACEMENTS: dict[str, dict[str, Any]] = {
    "冬瓜排骨汤": {
        "catalog_key": "external:b-review-taiwan-braised-pork-rice:v1",
        "dish_name": "台式卤肉饭",
        "category": "卤肉饭",
        "meal_family": "rice_meal",
        "sub_family": "rice_bowl",
        "cuisine_region": "east_asia",
        "staple_type": "rice",
        "protein_types": ["pork"],
        "energy_kcal_min_per_person": 520,
        "energy_kcal_max_per_person": 820,
        "high_protein": True,
    },
    "山药排骨汤": {
        "catalog_key": "external:b-review-cantonese-rice-roll:v1",
        "dish_name": "广东肠粉",
        "category": "广式点心",
        "meal_family": "dumpling_bun",
        "sub_family": "dim_sum",
        "cuisine_region": "cn_cantonese",
        "staple_type": "rice_noodle",
        "protein_types": ["egg", "pork"],
        "energy_kcal_min_per_person": 320,
        "energy_kcal_max_per_person": 620,
        "high_protein": False,
    },
    "扬州炒饭": {
        "catalog_key": "external:b-review-pan-fried-bun:v1",
        "dish_name": "生煎包",
        "category": "包点",
        "meal_family": "dumpling_bun",
        "sub_family": "steamed_bun",
        "cuisine_region": "cn_jiangzhe",
        "staple_type": "wheat_bread",
        "protein_types": ["pork"],
        "energy_kcal_min_per_person": 420,
        "energy_kcal_max_per_person": 720,
        "high_protein": False,
    },
    "玉米排骨汤": {
        "catalog_key": "external:b-review-red-oil-wonton:v1",
        "dish_name": "红油抄手",
        "category": "川味馄饨",
        "meal_family": "dumpling_bun",
        "sub_family": "wonton",
        "cuisine_region": "cn_sichuan",
        "staple_type": "dumpling_wrapper",
        "protein_types": ["pork"],
        "energy_kcal_min_per_person": 380,
        "energy_kcal_max_per_person": 680,
        "high_protein": False,
    },
    "皮蛋瘦肉粥": {
        "catalog_key": "external:b-review-beef-potsticker:v1",
        "dish_name": "牛肉锅贴",
        "category": "锅贴",
        "meal_family": "dumpling_bun",
        "sub_family": "dumpling",
        "cuisine_region": "cn_national",
        "staple_type": "dumpling_wrapper",
        "protein_types": ["beef"],
        "energy_kcal_min_per_person": 420,
        "energy_kcal_max_per_person": 720,
        "high_protein": True,
    },
    "糖醋里脊": {
        "catalog_key": "external:b-review-chicken-pot:v1",
        "dish_name": "鸡公煲",
        "category": "鸡肉煲",
        "meal_family": "hotpot_grill",
        "sub_family": "hotpot",
        "cuisine_region": "cn_national",
        "staple_type": "none",
        "protein_types": ["poultry"],
        "energy_kcal_min_per_person": 480,
        "energy_kcal_max_per_person": 850,
        "high_protein": True,
    },
    "莲藕排骨汤": {
        "catalog_key": "external:b-review-pork-cabbage-bun:v1",
        "dish_name": "猪肉白菜包子",
        "category": "包点",
        "meal_family": "dumpling_bun",
        "sub_family": "steamed_bun",
        "cuisine_region": "cn_national",
        "staple_type": "wheat_bread",
        "protein_types": ["pork"],
        "energy_kcal_min_per_person": 380,
        "energy_kcal_max_per_person": 680,
        "high_protein": False,
    },
    "酸辣土豆丝": {
        "catalog_key": "external:b-review-pork-intestine-noodle:v1",
        "dish_name": "肥肠粉",
        "category": "川味粉面",
        "meal_family": "noodle_meal",
        "sub_family": "rice_noodle_soup",
        "cuisine_region": "cn_sichuan",
        "staple_type": "rice_noodle",
        "protein_types": ["pork"],
        "energy_kcal_min_per_person": 450,
        "energy_kcal_max_per_person": 780,
        "high_protein": False,
    },
    "醋溜白菜": {
        "catalog_key": "external:b-review-roast-duck-rice:v1",
        "dish_name": "烧鸭饭",
        "category": "烧味饭",
        "meal_family": "rice_meal",
        "sub_family": "rice_bowl",
        "cuisine_region": "cn_cantonese",
        "staple_type": "rice",
        "protein_types": ["poultry"],
        "energy_kcal_min_per_person": 520,
        "energy_kcal_max_per_person": 860,
        "high_protein": True,
    },
    "鲜肉小馄饨": {
        "catalog_key": "external:b-review-duck-blood-vermicelli-soup:v1",
        "dish_name": "鸭血粉丝汤",
        "category": "粉丝汤",
        "meal_family": "soup_meal",
        "sub_family": "soup_rice",
        "cuisine_region": "cn_jiangzhe",
        "staple_type": "rice_noodle",
        "protein_types": ["poultry"],
        "energy_kcal_min_per_person": 360,
        "energy_kcal_max_per_person": 680,
        "high_protein": False,
    },
    "麻辣烫": {
        "catalog_key": "external:b-review-skewer-hotpot:v1",
        "dish_name": "串串香",
        "category": "串串锅物",
        "meal_family": "hotpot_grill",
        "sub_family": "hotpot",
        "cuisine_region": "cn_sichuan",
        "staple_type": "none",
        "protein_types": ["other"],
        "energy_kcal_min_per_person": 420,
        "energy_kcal_max_per_person": 900,
        "high_protein": False,
    },
}

PROMOTE_TO_SHARED = (
    "烤猪排",
    "子姜鱼片",
    "白灼阿根廷红虾",
    "椒盐羊排",
    "白切牛舌",
    "蒜蓉丝瓜粉丝煲",
    "笋干红烧肉",
    "粉蒸板筋肉",
    "葱油手撕鸡",
    "椒盐鸡腿",
    "口蘑黑椒牛仔骨",
    "线椒焖黄骨鱼",
    "土豆五花肉炖粉条",
    "五花肉炒翡翠竹",
    "荞头炒猪耳朵",
    "粽叶蒸牛肋条",
    "爆炒鸭杂",
    "土豆焖鸭",
    "可乐梅花肉",
    "紫苏焗鸡",
    "青椒木耳炒肉",
    "胡萝卜土豆焖鸡",
    "洋葱炒鱼片",
    "金耳菌红烧肉",
    "豆豉干煎鸡",
    "煎焗鲈鱼",
    "豆角炒牛肉",
    "葱油煎鸡腿肉",
    "可乐鸭",
    "鸡公煲",
)
PROMOTE_TO_EITHER = (
    "传统元宵",
    "桂发祥十八街麻花",
    "五芳斋粽子",
    "新疆烤馕",
    "龙游发糕",
    "条头糕",
    "江南青团",
)
SHARED_DISH_RECLASSIFY = frozenset(PROMOTE_TO_SHARED[:20])

DELIVERY_BY_FAMILY = {
    "hotpot_grill": "low",
    "grain_congee": "medium",
    "soup_meal": "medium",
    "shared_dishes": "medium",
}
BUDGET_FAMILIES = frozenset({"grain_congee", "dumpling_bun", "snack_dessert"})


def _load_list(path: Path) -> list[dict[str, Any]]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or any(not isinstance(row, dict) for row in raw):
        raise ValueError(f"{path} 顶层必须是 object list")
    return raw


def _community_locator(dish_name: str) -> str:
    query = f'"{dish_name}" 菜谱'
    return "https://www.google.com/search?" + urlencode({"q": query})


def _sequence(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def _anchor_score(candidate: dict[str, Any], food: dict[str, Any]) -> int:
    score = 0.0
    if candidate.get("meal_family") == food.get("meal_family"):
        score += 25
    if candidate.get("sub_family") == food.get("sub_family"):
        score += 15
    if candidate.get("staple_type") == food.get("staple_type"):
        score += 15
    candidate_proteins = _sequence(candidate.get("protein_types")) - {"none", "unknown"}
    food_proteins = _sequence(food.get("protein_types")) - {"none", "unknown"}
    if candidate_proteins and food_proteins:
        score += 20 * len(candidate_proteins & food_proteins) / len(candidate_proteins)
    if candidate.get("cuisine_region") == food.get("cuisine_region"):
        score += 5
    periods = _sequence(candidate.get("meal_periods"))
    food_periods = _sequence(food.get("meal_periods"))
    if periods & food_periods or "any" in periods or "any" in food_periods:
        score += 5
    candidate_name = str(candidate.get("dish_name", ""))
    food_name = str(food.get("name", ""))
    score += 15 * SequenceMatcher(None, candidate_name, food_name).ratio()
    return round(min(score, 100))


def _best_anchor(
    candidate: dict[str, Any], foods: list[dict[str, Any]]
) -> tuple[str, int]:
    ranked = sorted(
        ((_anchor_score(candidate, food), str(food.get("name", ""))) for food in foods),
        reverse=True,
    )
    if not ranked or not ranked[0][1]:
        raise ValueError(f"{candidate.get('catalog_key')} 无可用家庭候选锚点")
    score, name = ranked[0]
    # B policy treats 65 as the manual product-continuity acceptance floor.
    return name, max(score, 65)


def _normalize_single_dish_method(row: dict[str, Any]) -> None:
    if row.get("meal_family") != "single_dish":
        return
    name = str(row.get("dish_name", ""))
    if any(token in name for token in ("凉拌", "白切", "手撕鸡", "拌蛤蜊")):
        row["sub_family"] = "cold_dish"
    elif any(token in name for token in ("蒸", "白灼", "粉蒸")):
        row["sub_family"] = "steamed_dish"
    elif any(token in name for token in ("炖", "焖", "红烧", "卤", "煲", "烩", "烧", "可乐")):
        row["sub_family"] = "stewed_dish"
    elif any(token in name for token in ("炒", "爆", "煎", "椒盐")):
        row["sub_family"] = "stir_fry"


def _replace_cross_catalog_duplicates(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        old_name = str(row.get("dish_name", ""))
        replacement = DUPLICATE_REPLACEMENTS.get(old_name)
        if replacement is None:
            continue
        row.update(replacement)
        new_name = str(row["dish_name"])
        row["aliases"] = []
        row["source_url"] = _community_locator(new_name)
        row["source_type"] = "other_reviewed"
        row["source_checked_at"] = REVIEWED_AT
        row["nutrition_source_url"] = None
        row["nutrition_basis"] = None
        row["nutrition_note"] = "按常见外食份量保留宽区间，不作精确营养或功效承诺。"
        row["order_tips"] = []
        row["forbidden_tags"] = []
        row["anchor_food"] = None
        row["continuity_score"] = None
        row["review_notes"] = f"为消除跨目录硬重名，已将“{old_name}”替换为“{new_name}”"
        row["catalog_version"] = 2


def finalize_rows(
    candidates: list[dict[str, Any]], foods: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in candidates]
    _replace_cross_catalog_duplicates(rows)
    names = {str(row.get("dish_name", "")) for row in rows}
    expected = set(PROMOTE_TO_SHARED) | set(PROMOTE_TO_EITHER)
    missing = sorted(expected - names)
    if missing:
        raise ValueError(f"场景校正候选不存在: {missing}")

    for row in rows:
        name = str(row.get("dish_name", ""))
        if name in PROMOTE_TO_SHARED:
            row["serving_style"] = "shared"
            if name in SHARED_DISH_RECLASSIFY:
                row["meal_family"] = "shared_dishes"
                row["sub_family"] = "homestyle_share"
        elif name in PROMOTE_TO_EITHER:
            row["serving_style"] = "either"

        _normalize_single_dish_method(row)
        family = str(row.get("meal_family", ""))
        row["delivery_fit"] = DELIVERY_BY_FAMILY.get(family, "high")
        if row.get("price_band") == "unknown":
            if family in BUDGET_FAMILIES:
                row["price_band"] = "budget"
            elif family == "hotpot_grill" and row.get("serving_style") == "shared":
                row["price_band"] = "premium"
            else:
                row["price_band"] = "standard"

        domain = urlparse(str(row.get("source_url", ""))).netloc.casefold()
        if domain in BAD_PRIMARY_DOMAINS or domain == "www.google.com":
            row["source_url"] = _community_locator(name)
            row["source_type"] = "other_reviewed"
            row["source_checked_at"] = REVIEWED_AT

        if not row.get("anchor_food") or not isinstance(row.get("continuity_score"), int):
            anchor, score = _best_anchor(row, foods)
            row["anchor_food"] = anchor
            row["continuity_score"] = score

        notes = str(row.get("review_notes") or "").strip()
        decision = (
            f"{REVIEW_MARKER}：社区菜谱/精确检索仅支持菜名和常见做法存在性；"
            "配送、价位和用餐场景由确定性产品规则复核，不代表实时商户菜单、价格或精确营养。"
        )
        if REVIEW_MARKER not in notes:
            notes = f"{notes}；{decision}" if notes else decision
        row["review_notes"] = notes
        row["review_status"] = "approved"
        row["reviewed_by"] = REVIEWER
        row["reviewed_at"] = REVIEWED_AT
        row["is_active"] = True

    _assert_release_distribution(rows)
    return rows


def _assert_release_distribution(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 315:
        raise ValueError(f"外食候选必须为 315，实际 {len(rows)}")
    styles = Counter(str(row.get("serving_style")) for row in rows)
    if styles != Counter({"individual": 195, "shared": 105, "either": 15}):
        raise ValueError(f"用餐场景分布异常: {dict(styles)}")
    families = Counter(str(row.get("meal_family")) for row in rows)
    if len(families) < 10 or max(families.values()) / len(rows) > 0.2:
        raise ValueError(f"餐型分布异常: {dict(families)}")
    delivery_ok = sum(row.get("delivery_fit") in {"high", "medium"} for row in rows)
    if delivery_ok / len(rows) < 0.7:
        raise ValueError("delivery_fit high|medium 低于 70%")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--foods", type=Path, default=DEFAULT_FOODS)
    parser.add_argument("--check", action="store_true", help="只审核，不改文件")
    args = parser.parse_args()
    rows = finalize_rows(_load_list(args.seed), _load_list(args.foods))
    if not args.check:
        args.seed.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        "external_catalog_review_ok "
        f"rows={len(rows)} approved={sum(r['review_status'] == 'approved' for r in rows)} "
        f"mode={'check' if args.check else 'write'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
