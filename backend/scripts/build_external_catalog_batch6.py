"""Append 52 ordinary recipe candidates from Meishichina pages (batch 6).

The source is a public recipe/community index. Rows are discovery drafts only;
merchant availability, delivery fit, portion and nutrition still require review.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "backend" / "data" / "external_dining_seed.json"
CHECKED_AT = "2026-09-01T00:20:00+08:00"
I = ["lunch", "dinner"]
ID = ["lunch", "dinner", "late_night"]
B = ["breakfast", "lunch", "dinner"]


def make(item: tuple) -> dict:
    key, name, family, sub, region, staple, proteins, style, periods, anchor, score, energy, recipe_id, note = item
    return {
        "catalog_key": f"external:batch6-{key}:v1", "legacy_key": None,
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
    ("carrot-potato-chicken", "胡萝卜土豆焖鸡", "single_dish", "stewed_dish", "cn_national", "tuber", ["poultry"], "individual", I, "鸡肉时蔬饭", 84, (500, 900), 666214, "禽肉、土豆和焖制结构接近现有鸡肉饭。"),
    ("beef-fish-kimchi-pot", "牛肉鱼片泡菜锅", "hotpot_grill", "hotpot", "cn_national", "none", ["beef", "fish"], "shared", ID, "清汤牛肉锅＋菌菇蔬菜拼盘＋主食", 78, (600, 1100), 666674, "双蛋白锅物可按人数调整，辣度和过敏原待审核。"),
    ("dried-shrimp-lettuce", "海米烧莴笋", "single_dish", "stir_fry", "cn_national", "none", ["crustacean"], "individual", I, "虾仁滑蛋饭配时蔬", 76, (220, 480), 667067, "海鲜过敏原与莴笋供应待审核。"),
    ("pork-potato-chive-pie", "鲜肉土豆韭菜麦饼", "wrap_light_meal", "wrap", "cn_national", "wheat_bread", ["pork"], "individual", B, "鸡蛋蔬菜卷配玉米", 78, (420, 780), 667060, "面饼早餐结构接近卷饼，油量和份量待审核。"),
    ("onion-fish-slices", "洋葱炒鱼片", "single_dish", "stir_fry", "cn_national", "none", ["fish"], "individual", I, "清蒸鱼＋时蔬＋杂粮饭", 82, (340, 680), 666125, "鱼片小炒与现有鱼餐连续，鱼种待审核。"),
    ("beef-cabbage-ricecake", "牛肉白菜煮年糕", "rice_meal", "rice_bowl", "cn_national", "mixed", ["beef"], "individual", I, "黑椒牛柳饭配彩椒", 80, (500, 900), 666143, "牛肉与主食结构明确，年糕份量待审核。"),
    ("beef-mixed-noodle", "牛肉拌面", "noodle_meal", "dry_noodle", "cn_national", "wheat_noodle", ["beef"], "individual", I, "炸酱面", 86, (500, 860), 666126, "牛肉面食与现有清汤/炸酱面连续，酱料待审核。"),
    ("minced-pork-taro", "肉沫芋仔", "single_dish", "stewed_dish", "cn_national", "tuber", ["pork"], "individual", I, "香煎豆腐杂蔬饭", 78, (420, 760), 666175, "肉沫加芋头结构明确，份量待审核。"),
    ("garlic-chive-shrimp", "蒜苔炒海米", "single_dish", "stir_fry", "cn_national", "none", ["crustacean"], "individual", I, "虾仁滑蛋饭配时蔬", 78, (240, 520), 667063, "海米过敏原和盐分待审核。"),
    ("golden-fungus-braised-pork", "金耳菌红烧肉", "single_dish", "stewed_dish", "cn_national", "none", ["pork"], "individual", I, "红烧肉", 86, (560, 980), 666190, "红烧肉锚点明确，菌菇供应与盐分待审核。"),
    ("lei-pepper-pork-trotter", "擂辣椒烧猪脚", "single_dish", "stewed_dish", "cn_hunan", "none", ["pork"], "shared", I, "砂锅鸡煲＋双份青菜＋米饭", 78, (650, 1150), 666660, "共享炖菜结构明确，骨头和辣度待审核。"),
    ("crispy-potato-rice-wrap", "脆脆小土豆饭包", "wrap_light_meal", "wrap", "cn_northeast", "rice", ["none"], "individual", B, "鸡蛋蔬菜卷配玉米", 76, (360, 680), 667054, "米饭卷结构接近卷饼，土豆和油量待审核。"),
    ("fermented-beanpan-fried-chicken", "豆豉干煎鸡", "single_dish", "stir_fry", "cn_cantonese", "none", ["poultry"], "individual", I, "鸡腿肉蔬菜糙米饭", 82, (450, 820), 666191, "鸡肉与煎制结构连续，豆豉盐分待审核。"),
    ("ham-potato-cake", "火腿肠土豆饼", "wrap_light_meal", "wrap", "cn_national", "tuber", ["pork"], "individual", B, "鸡蛋蔬菜卷配玉米", 74, (360, 700), 666200, "早餐饼类存在性明确，品牌食材不外推。"),
    ("mushroom-beef-ricecake", "口蘑牛肉煮年糕", "rice_meal", "rice_bowl", "cn_national", "mixed", ["beef"], "individual", I, "黑椒牛柳饭配彩椒", 80, (500, 900), 666174, "牛肉、菌菇与主食结构接近盖饭，份量待审核。"),
    ("cured-meat-fresh-bamboo-soup", "腌笃鲜", "soup_meal", "stew_soup_set", "cn_jiangzhe", "none", ["pork"], "shared", I, "莲藕排骨汤配时蔬饭", 82, (340, 700), 667025, "江南汤餐可作为共享扩展，咸度待审核。"),
    ("chive-dried-shrimp", "韭菜炒海米", "single_dish", "stir_fry", "cn_national", "none", ["crustacean"], "individual", I, "虾仁滑蛋饭配时蔬", 76, (220, 500), 667047, "海米过敏原和油量待审核。"),
    ("tomato-potato-mince", "番茄土豆泥肉沫", "rice_meal", "rice_bowl", "cn_national", "tuber", ["pork"], "individual", I, "番茄鸡蛋盖饭", 82, (420, 780), 666637, "番茄、土豆和肉沫结构连续，主食搭配待审核。"),
    ("mixed-vegetable-glass-noodle", "杂菜拌粉条", "noodle_meal", "dry_noodle", "cn_national", "rice_noodle", ["none"], "individual", I, "三鲜米线配青菜", 78, (330, 620), 666185, "粉条和蔬菜结构清晰，调味和配送待审核。"),
    ("cured-bean-rice", "腊味蚕豆焖饭", "rice_meal", "braised_rice", "cn_jiangzhe", "rice", ["pork", "legume"], "individual", I, "腊味煲仔饭配青菜", 82, (560, 980), 667036, "焖饭锚点明确，腊味盐分待审核。"),
    ("pan-fried-seabass", "煎焗鲈鱼", "single_dish", "steamed_dish", "cn_cantonese", "none", ["fish"], "individual", I, "清蒸鱼＋时蔬＋杂粮饭", 84, (420, 820), 666178, "鱼类煎焗结构连续，鱼种和油量待审核。"),
    ("bell-pepper-clam", "彩椒拌蛤蜊肉", "single_dish", "cold_dish", "cn_national", "none", ["mollusk"], "individual", I, "鸡肉蔬菜沙拉配玉米", 76, (260, 560), 667027, "贝类过敏原和冷菜配送待审核。"),
    ("green-bean-beef-stirfry", "豆角炒牛肉", "single_dish", "stir_fry", "cn_national", "none", ["beef"], "individual", I, "黑椒牛柳饭配彩椒", 84, (420, 800), 666124, "牛肉和蔬菜小炒与现有结构连续。"),
    ("malantou-scrambled-egg", "马兰头炒鸡蛋", "single_dish", "stir_fry", "cn_jiangzhe", "none", ["egg"], "individual", I, "番茄滑蛋牛肉饭", 78, (240, 520), 667024, "蛋类与时蔬结构明确，季节性不外推。"),
    ("mince-potato-mash", "肉沫土豆泥", "single_dish", "stewed_dish", "cn_national", "tuber", ["pork"], "individual", I, "番茄鸡蛋盖饭", 80, (380, 720), 666451, "土豆与肉沫结构连续，酱汁待审核。"),
    ("lei-pepper-rib", "擂辣椒烧排骨", "single_dish", "stewed_dish", "cn_hunan", "none", ["pork"], "shared", I, "莲藕排骨汤配时蔬饭", 80, (560, 980), 666422, "排骨共享菜扩展，辣度和份量待审核。"),
    ("beef-chicken-feet-pot", "牛腩烧鸡爪", "single_dish", "stewed_dish", "cn_national", "none", ["beef", "poultry"], "shared", I, "砂锅鸡煲＋双份青菜＋米饭", 76, (620, 1100), 666450, "双蛋白炖菜适合多人，骨头与份量待审核。"),
    ("scallion-pan-chicken", "葱油煎鸡腿肉", "single_dish", "stir_fry", "cn_national", "none", ["poultry"], "individual", I, "鸡腿肉蔬菜糙米饭", 84, (440, 820), 666420, "鸡腿肉与现有鸡肉饭连续，油量待审核。"),
    ("cola-pork-trotter", "可乐猪脚", "single_dish", "stewed_dish", "cn_national", "none", ["pork"], "shared", I, "砂锅鸡煲＋双份青菜＋米饭", 76, (650, 1150), 666419, "共享炖菜存在性明确，不外推健康属性。"),
    ("wuzhimaotao-braised-duck", "五指毛桃焖鸭", "single_dish", "stewed_dish", "cn_cantonese", "none", ["poultry"], "shared", I, "大盘鸡小份＋拌青菜＋面或米饭", 74, (520, 980), 666397, "焖鸭结构连续；不使用未经证实的功效标签。"),
    ("potato-wide-noodle-beef", "土豆宽粉炖牛腩", "noodle_meal", "noodle_soup", "cn_national", "rice_noodle", ["beef"], "shared", I, "清汤牛肉面", 82, (600, 1100), 666385, "牛腩、宽粉和汤底适合共享，盐分待审核。"),
    ("winter-melon-pork-soup", "雪菜冬瓜汤", "soup_meal", "light_soup_set", "cn_jiangzhe", "none", ["pork"], "individual", I, "冬瓜虾仁汤配杂粮饭", 80, (180, 460), 666876, "冬瓜汤与现有清淡汤餐连续，盐分待审核。"),
    ("water-pan-bun", "水煎包", "dumpling_bun", "steamed_bun", "cn_national", "wheat_bread", ["pork"], "individual", B, "小笼包", 84, (380, 720), 666984, "包点结构明确，煎制油量和份量待审核。"),
    ("radish-veg-bun", "萝卜馅素包子", "dumpling_bun", "steamed_bun", "cn_national", "wheat_bread", ["none"], "individual", B, "小笼包", 80, (300, 580), 666799, "素馅包点补足早餐品类，馅料和份量待审核。"),
    ("red-braised-pork-glass-noodle", "红烧肉炖粉条", "single_dish", "stewed_dish", "cn_northeast", "rice_noodle", ["pork"], "shared", I, "红烧肉", 86, (600, 1100), 666320, "红烧肉锚点明确，粉条份量待审核。"),
    ("potato-braised-pork-trotter", "土豆焖猪脚", "single_dish", "stewed_dish", "cn_national", "tuber", ["pork"], "shared", I, "砂锅鸡煲＋双份青菜＋米饭", 78, (620, 1120), 666324, "共享炖菜结构明确，骨头与可食份量待审核。"),
    ("hand-pulled-stir-noodle", "炒手扯面", "noodle_meal", "stir_fried_noodle", "cn_northwest", "wheat_noodle", ["none"], "individual", I, "油泼面", 82, (420, 780), 666311, "面食结构连续，油辣度待审核。"),
    ("orange-chicken-wing", "橙香鸡翅", "single_dish", "stewed_dish", "cn_national", "none", ["poultry"], "individual", I, "鸡肉时蔬饭", 78, (420, 800), 666937, "鸡翅和果香炖制存在性明确，糖分待审核。"),
    ("spinach-egg-veg-pie", "菠菜鸡蛋馅菜盒", "wrap_light_meal", "wrap", "cn_national", "wheat_bread", ["egg"], "individual", B, "鸡蛋蔬菜卷配玉米", 80, (380, 720), 666946, "面皮和蛋菜馅结构接近早餐卷，油量待审核。"),
    ("sauce-pork-belly-chicken", "酱香猪肚鸡", "soup_meal", "stew_soup_set", "cn_cantonese", "none", ["pork", "poultry"], "shared", I, "清汤牛肉锅＋菌菇蔬菜拼盘＋主食", 78, (620, 1100), 666308, "共享汤锅结构明确，内脏接受度与份量待审核。"),
    ("cola-duck", "可乐鸭", "single_dish", "stewed_dish", "cn_national", "none", ["poultry"], "individual", I, "大盘鸡小份＋拌青菜＋面或米饭", 74, (500, 920), 666302, "禽肉炖制与现有鸡鸭类连续，不外推健康属性。"),
    ("passionfruit-tomato-fish", "百香果番茄鱼", "single_dish", "stewed_dish", "cn_national", "none", ["fish"], "shared", I, "番茄牛腩锅＋凉热双蔬＋主食", 80, (460, 900), 666301, "番茄鱼锅与现有鱼餐连续，酸度和鱼种待审核。"),
    ("pineapple-beef-roll", "菠萝肥牛卷", "hotpot_grill", "hotpot", "cn_national", "none", ["beef"], "either", ID, "清汤牛肉锅＋菌菇蔬菜拼盘＋主食", 78, (420, 860), 666729, "肥牛锅物结构明确，水果甜度与过敏原待审核。"),
    ("cured-pea-egg-fried-rice", "腊肉豌豆鸡蛋炒饭", "rice_meal", "fried_rice", "cn_national", "rice", ["pork", "egg", "legume"], "individual", I, "扬州炒饭", 84, (520, 900), 666931, "炒饭锚点明确，腊肉盐分待审核。"),
    ("mushroom-tomato-fish", "海鲜菇番茄鱼片", "single_dish", "stewed_dish", "cn_national", "none", ["fish"], "shared", I, "番茄牛腩锅＋凉热双蔬＋主食", 82, (420, 820), 666929, "鱼片加菌菇汤锅结构连续，鱼种待审核。"),
    ("oyster-seaweed-egg", "蚝仔紫菜煎蛋", "single_dish", "stir_fry", "cn_fujian", "none", ["mollusk", "egg"], "individual", I, "番茄滑蛋牛肉饭", 78, (300, 620), 666277, "蛋和海鲜结构明确，贝类过敏原待审核。"),
    ("spicy-sour-potato", "酸辣土豆丝", "single_dish", "stir_fry", "cn_national", "tuber", ["none"], "individual", I, "什锦素烩菜＋蒸蛋＋杂粮饭", 84, (160, 360), 666912, "常见蔬菜小炒，酸辣度和配送待审核。"),
    ("potato-wide-noodle-chicken", "土豆宽粉焖鸡", "noodle_meal", "noodle_soup", "cn_national", "rice_noodle", ["poultry"], "shared", I, "大盘鸡小份＋拌青菜＋面或米饭", 82, (600, 1100), 666258, "禽肉、土豆和宽粉结构接近大盘鸡，辣度待审核。"),
    ("sweet-sour-pork-tenderloin", "糖醋里脊", "single_dish", "stir_fry", "cn_national", "none", ["pork"], "individual", I, "红烧肉", 80, (440, 820), 666916, "猪肉家常菜存在性明确，糖醋口味和油量待审核。"),
    ("shage-braised-pork-stomach", "沙葛焖猪肚", "single_dish", "stewed_dish", "cn_cantonese", "none", ["pork"], "shared", I, "酱香猪肚鸡", 76, (520, 980), 666257, "内脏炖菜结构连续，不外推功效标签。"),
    ("salted-meat-bamboo-shoot", "咸肉炖春笋", "single_dish", "stewed_dish", "cn_jiangzhe", "none", ["pork"], "shared", I, "清炖狮子头＋双份时蔬＋米饭", 80, (500, 920), 666896, "江南炖菜结构明确，季节供应与盐分待审核。"),
    ("morel-rib-congee", "羊肚菌排骨粥", "grain_congee", "congee", "cn_national", "congee", ["pork"], "shared", B, "南瓜小米粥配蒸蛋", 82, (320, 640), 666247, "粥品和排骨结构接近现有早餐粥，菌菇供应待审核。"),
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
    print(f"candidate_batch6_ok added={added} total={len(rows)} status=draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
