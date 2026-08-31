"""Append a small source-backed batch from the official ICH tofu page.

The page explicitly names three tofu dishes and several processed tofu foods,
but it does not establish restaurant availability, portions, delivery fitness,
or nutrition. These rows therefore remain ``draft`` and are not eligible
for production recommendation until a separate menu/content review.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "external_dining_seed.json"
SOURCE_URL = "https://www.ihchina.cn/project_details/23813.html"
CHECKED_AT = "2026-08-31T18:55:00+08:00"


def _row(
    key: str,
    name: str,
    category: str,
    family: str,
    sub_family: str,
    staple: str,
    proteins: list[str],
    style: str,
    periods: list[str],
    anchor: str,
    score: int,
    energy: tuple[int, int],
    note: str,
) -> dict[str, object]:
    return {
        "catalog_key": f"external:batch3-{key}:v1",
        "legacy_key": None,
        "dish_name": name,
        "aliases": [],
        "category": category,
        "meal_family": family,
        "sub_family": sub_family,
        "cuisine_region": "cn_shandong",
        "staple_type": staple,
        "protein_types": proteins,
        "serving_style": style,
        "meal_periods": periods,
        "delivery_fit": "unknown",
        "price_band": "unknown",
        "nature": "unknown",
        "seasonal_solar_terms": ["all_season"],
        "source_url": SOURCE_URL,
        "source_type": "original_publisher",
        "source_checked_at": CHECKED_AT,
        "nutrition_source_url": None,
        "nutrition_basis": None,
        "review_status": "draft",
        "reviewed_by": None,
        "reviewed_at": None,
        "review_notes": (
            "来源核验：中国非遗网‘豆腐传统制作技艺’页面明确列出该名称；"
            "仅作候选发现依据，未从页面推断菜单、份量、配送、营养或功效。"
            + note
        ),
        "is_active": True,
        "catalog_version": 1,
        "taxonomy_version": 1,
        "forbidden_tags": [],
        "energy_kcal_min_per_person": energy[0],
        "energy_kcal_max_per_person": energy[1],
        "nutrition_note": "待按实际菜单份量复核；当前不作精确营养承诺。",
        "order_tips": [],
        "high_protein": False,
        "anchor_food": anchor,
        "continuity_score": score,
    }


BATCH: list[dict[str, object]] = [
    _row("taishan-tofu-balls", "泰山豆腐丸子", "地方豆腐菜", "single_dish", "stewed_dish", "none", ["soy"], "individual", ["lunch", "dinner"], "家常豆腐", 86, (220, 420), "正文将其列为以豆腐为主料的泰山菜品；丸子配料和菜单份型待审核。"),
    _row("yipin-tofu", "一品豆腐", "地方豆腐菜", "single_dish", "stewed_dish", "none", ["soy"], "individual", ["lunch", "dinner"], "家常豆腐", 84, (180, 360), "正文将其列为以豆腐为主料的泰山菜品；具体配料待审核。"),
    _row("furong-tofu", "芙蓉豆腐", "地方豆腐菜", "single_dish", "steamed_dish", "none", ["soy"], "individual", ["lunch", "dinner"], "香煎豆腐杂蔬饭", 82, (180, 360), "正文将其列为以豆腐为主料的泰山菜品；不把‘芙蓉’外推为鸡蛋或其他食材。"),
    _row("fermented-tofu", "豆腐乳", "传统豆制品", "snack_dessert", "snack", "none", ["soy"], "individual", ["breakfast", "snack"], "霉豆腐风味小菜拼盘", 72, (80, 220), "正文列为豆腐再加工食品；是否作为独立外食选项需产品审核。"),
    _row("dried-tofu", "豆腐干", "传统豆制品", "snack_dessert", "snack", "none", ["soy"], "individual", ["breakfast", "snack"], "香煎豆腐杂蔬饭", 74, (100, 280), "正文列为豆腐再加工食品；具体口味和份型待审核。"),
    _row("stinky-tofu", "臭豆腐", "地方豆制小吃", "snack_dessert", "snack", "none", ["soy"], "individual", ["snack", "late_night"], "香煎豆腐杂蔬饭", 76, (180, 420), "正文列为豆腐再加工食品；油炸/蒸制差异和配送适配待审核。"),
    _row("five-spice-tofu", "五香豆腐", "传统豆制品", "single_dish", "stewed_dish", "none", ["soy"], "individual", ["lunch", "dinner"], "家常豆腐", 78, (150, 340), "正文列为豆腐再加工食品；未从名称推断具体卤制配方。"),
    _row("spicy-tofu", "麻辣豆腐", "地方豆腐菜", "single_dish", "stir_fry", "none", ["soy"], "individual", ["lunch", "dinner"], "麻婆豆腐饭配青菜", 80, (180, 420), "正文列为豆腐再加工食品；辣度和是否含肉待审核。"),
    _row("frozen-tofu", "冻豆腐", "传统豆制品", "soup_meal", "light_soup_set", "none", ["soy"], "individual", ["lunch", "dinner"], "冬瓜虾仁汤配杂粮饭", 76, (120, 320), "正文列为豆腐再加工食品；汤底、配菜和供应方式待审核。"),
    _row("tea-tofu", "茶豆腐", "地方豆制品", "snack_dessert", "snack", "none", ["soy"], "individual", ["breakfast", "snack"], "香煎豆腐杂蔬饭", 70, (100, 280), "正文列为豆腐再加工食品；茶香工艺和菜单形态待审核。"),
]


def main() -> int:
    rows = json.loads(SEED.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("external seed 顶层必须是 list")
    existing = {item.get("catalog_key") for item in rows if isinstance(item, dict)}
    added = 0
    for item in BATCH:
        if item["catalog_key"] in existing:
            continue
        rows.append(item)
        existing.add(item["catalog_key"])
        added += 1
    SEED.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"candidate_batch3_ok added={added} total={len(rows)} status=draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
