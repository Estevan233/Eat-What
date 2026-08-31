"""Append the final 26 discovery drafts for the 315-row external target."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "backend" / "data" / "external_dining_seed.json"
CHECKED_AT = "2026-09-01T01:10:00+08:00"
I = ["lunch", "dinner"]
ID = ["lunch", "dinner", "late_night"]
B = ["breakfast", "lunch", "dinner"]


def make(item: tuple) -> dict:
    key, name, family, sub, region, staple, proteins, style, periods, anchor, score, energy, recipe_id, note = item
    return {
        "catalog_key": f"external:batch7-{key}:v1", "legacy_key": None,
        "dish_name": name, "aliases": [], "category": family,
        "meal_family": family, "sub_family": sub, "cuisine_region": region,
        "staple_type": staple, "protein_types": proteins,
        "serving_style": style, "meal_periods": periods,
        "delivery_fit": "unknown", "price_band": "unknown", "nature": "unknown",
        "seasonal_solar_terms": ["all_season"],
        "source_url": f"https://home.meishichina.com/recipe-{recipe_id}.html",
        "source_type": "other_reviewed", "source_checked_at": CHECKED_AT,
        "nutrition_source_url": None, "nutrition_basis": None,
        "review_status": "draft", "reviewed_by": None, "reviewed_at": None,
        "review_notes": (
            "来源核验：美食天下公开菜谱页，作为菜名/做法存在性的候选发现来源；"
            "不把社区食谱当作商户菜单、价格、配送或营养证明。" + note
        ),
        "is_active": True, "catalog_version": 1, "taxonomy_version": 1,
        "forbidden_tags": [], "energy_kcal_min_per_person": energy[0],
        "energy_kcal_max_per_person": energy[1],
        "nutrition_note": "待按实际菜单份量复核；当前不作精确营养或功效承诺。",
        "order_tips": [], "high_protein": any(p in {
            "poultry", "pork", "beef", "lamb", "fish", "crustacean", "mollusk"
        } for p in proteins),
        "anchor_food": anchor, "continuity_score": score,
    }


# (key,name,family,sub,region,staple,proteins,style,periods,anchor,score,(min,max),recipe_id,note)
BATCH = [
    ("beef-shiitake-noodle", "牛肉香菇面", "noodle_meal", "noodle_soup", "cn_national", "wheat_noodle", ["beef"], "individual", I, "清汤牛肉面", 86, (500, 860), 667622, "牛肉、菌菇和面食结构连续，汤底盐分待审核。"),
    ("beer-spicy-crab", "啤酒香辣蟹", "hotpot_grill", "hotpot", "cn_national", "none", ["crustacean"], "shared", ID, "清汤牛肉锅＋菌菇蔬菜拼盘＋主食", 76, (650, 1200), 667606, "海鲜共享菜存在性明确，辣度和过敏原待审核。"),
    ("yangyu-caca", "洋芋擦擦", "wrap_light_meal", "wrap", "cn_northwest", "tuber", ["none"], "individual", B, "鸡蛋蔬菜卷配玉米", 78, (320, 640), 667603, "土豆主食替代性明确，油量和份量待审核。"),
    ("thin-veg-roll", "薄皮大馅素菜卷", "wrap_light_meal", "wrap", "cn_national", "wheat_bread", ["none"], "individual", B, "鸡蛋蔬菜卷配玉米", 82, (320, 640), 667573, "蔬菜卷结构接近卷饼，馅料与油量待审核。"),
    ("tomato-potato-beef-stew", "番茄土豆炖牛肉", "single_dish", "stewed_dish", "cn_national", "tuber", ["beef"], "shared", I, "番茄牛腩锅＋凉热双蔬＋主食", 88, (560, 1000), 667454, "番茄牛肉炖菜与现有牛腩锅连续，份量待审核。"),
    ("roast-chicken-breast-veg", "时蔬烤鸡胸肉", "set_meal", "roast_set", "cn_national", "none", ["poultry"], "individual", I, "烤鸡腿土豆时蔬套餐", 86, (360, 700), 667499, "高蛋白套餐候选，实际营养和份量待复核。"),
    ("seafood-veg-congee", "时蔬海鲜粥", "grain_congee", "congee", "cn_cantonese", "congee", ["crustacean", "fish"], "shared", B, "南瓜小米粥配蒸蛋", 82, (320, 680), 667470, "海鲜粥与现有粥品连续，过敏原待审核。"),
    ("egg-braised-noodle", "荷包蛋焖面", "noodle_meal", "dry_noodle", "cn_national", "wheat_noodle", ["egg"], "individual", I, "番茄鸡蛋面配青菜", 84, (400, 760), 667440, "蛋面结构与现有面食连续，油盐待审核。"),
    ("corn-yam-pork-stomach-soup", "玉米山药猪肚汤", "soup_meal", "stew_soup_set", "cn_national", "none", ["pork"], "shared", I, "酱香猪肚鸡", 80, (360, 760), 667424, "共享汤餐结构明确，不外推滋补功效。"),
    ("tomato-potato-lumpy-soup", "番茄土豆疙瘩汤", "soup_meal", "soup_rice", "cn_national", "wheat_bread", ["egg"], "individual", I, "番茄牛腩粉", 82, (300, 620), 667397, "番茄、蛋和面疙瘩结构接近汤餐，份量待审核。"),
    ("carrot-egg-pancake", "胡萝卜丝煎蛋", "single_dish", "stir_fry", "cn_national", "none", ["egg"], "individual", B, "番茄滑蛋牛肉饭", 78, (220, 480), 667225, "蛋和蔬菜结构清晰，煎制油量待审核。"),
    ("dry-fried-cauliflower", "干煸菜花", "single_dish", "stir_fry", "cn_national", "none", ["none"], "individual", I, "什锦素烩菜＋蒸蛋＋杂粮饭", 80, (220, 500), 667257, "常见蔬菜小炒，油量和辣度待审核。"),
    ("five-spice-peanuts", "五香卤花生", "snack_dessert", "snack", "cn_national", "none", ["nut_seed"], "either", ID, "四川泡菜小菜拼盘", 72, (260, 520), 667374, "小吃/配菜存在性明确，坚果过敏原待审核。"),
    ("corn-chicken-wing-pot", "玉米鸡翅煲", "single_dish", "stewed_dish", "cn_national", "corn", ["poultry"], "shared", I, "砂锅鸡煲＋双份青菜＋米饭", 84, (560, 980), 667371, "鸡翅煲适合共享，骨头和份量待审核。"),
    ("cold-edamame", "凉拌毛豆", "single_dish", "cold_dish", "cn_national", "none", ["legume"], "either", I, "鸡肉蔬菜沙拉配玉米", 78, (160, 360), 667363, "常见凉菜，豆类过敏原与配送待审核。"),
    ("southern-shacha-noodle", "闽南沙茶面", "noodle_meal", "noodle_soup", "cn_fujian", "wheat_noodle", ["pork", "crustacean"], "individual", I, "云吞面配白灼菜", 86, (500, 900), 667362, "闽南面食与现有汤面连续，海鲜过敏原待审核。"),
    ("mushroom-wintermelon-beef-soup", "口蘑冬瓜牛肉汤", "soup_meal", "light_soup_set", "cn_national", "none", ["beef"], "shared", I, "冬瓜虾仁汤配杂粮饭", 84, (260, 560), 667351, "牛肉、冬瓜和菌菇结构明确，盐分待审核。"),
    ("pepper-salt-chicken-crispy", "鸡胸肉版椒盐小酥肉", "single_dish", "stir_fry", "cn_national", "none", ["poultry"], "individual", I, "鸡腿肉蔬菜糙米饭", 80, (420, 780), 667349, "鸡胸肉轻量化方向，油炸方式和份量待审核。"),
    ("shiitake-celery-pork-bun", "香菇芹菜酱肉包", "dumpling_bun", "steamed_bun", "cn_national", "wheat_bread", ["pork"], "individual", B, "小笼包", 82, (360, 700), 606281, "香菇、芹菜和包点结构明确，盐分待审核。"),
    ("garlic-chicken-wing", "蒜香鸡翅", "single_dish", "stir_fry", "cn_national", "none", ["poultry"], "individual", I, "鸡肉时蔬饭", 82, (420, 800), 606293, "鸡翅菜名和做法明确，油量待审核。"),
    ("seaweed-wonton-soup", "紫菜馄饨皮汤", "soup_meal", "light_soup_set", "cn_national", "dumpling_wrapper", ["egg"], "individual", I, "鲜虾蔬菜馄饨", 80, (220, 480), 606294, "馄饨皮汤与现有汤餐连续，盐分待审核。"),
    ("hot-wonton-soup", "热汤云吞", "dumpling_bun", "wonton", "cn_cantonese", "dumpling_wrapper", ["pork"], "individual", I, "云吞面配白灼菜", 84, (300, 620), 558614, "云吞汤与现有云吞面连续，份量待审核。"),
    ("luncheon-veg-shrimp-noodle", "午餐肉青菜虾仔面", "noodle_meal", "noodle_soup", "cn_cantonese", "wheat_noodle", ["pork", "crustacean"], "individual", I, "鸡肉蔬菜河粉", 78, (480, 860), 558616, "面、青菜和双蛋白结构明确，过敏原待审核。"),
    ("celery-redpepper-pork", "芹菜红椒炒肉丝", "single_dish", "stir_fry", "cn_national", "none", ["pork"], "individual", I, "肉末茄子饭配青菜", 84, (380, 720), 415990, "家常肉丝与现有小炒连续，辣度待审核。"),
    ("three-cup-shrimp", "三杯虾", "single_dish", "stir_fry", "cn_fujian", "none", ["crustacean"], "shared", I, "虾仁滑蛋饭配时蔬", 78, (420, 780), 345821, "海鲜共享菜存在性明确，酱汁和过敏原待审核。"),
    ("farmer-stirfried-pork", "农家小炒肉", "single_dish", "stir_fry", "cn_hunan", "none", ["pork"], "shared", I, "湘味小炒肉＋蒸蛋＋时蔬＋米饭", 88, (520, 900), 345955, "湘味小炒与现有猪肉菜连续，辣度待审核。"),
]


def main() -> int:
    rows = json.loads(SEED.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("external seed 顶层必须是 list")
    existing = {x.get("catalog_key") for x in rows if isinstance(x, dict)}
    added = 0
    for values in BATCH:
        item = make(values)
        if item["catalog_key"] in existing:
            continue
        rows.append(item)
        existing.add(item["catalog_key"])
        added += 1
    SEED.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"candidate_batch7_ok added={added} total={len(rows)} status=draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
