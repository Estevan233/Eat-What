"""Append 52 mainstream recipe candidates sourced from Meishichina pages.

Meishichina pages are public recipe/community content. They establish a
recipe-name and cooking-method lead only; every row remains ``draft`` until a
merchant/menu check and content review are completed.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "backend" / "data" / "external_dining_seed.json"
CHECKED_AT = "2026-08-31T23:55:00+08:00"


def row(key, name, category, family, sub, region, staple, proteins, style, periods, anchor, score, energy, url, note):
    return {
        "catalog_key": f"external:batch5-{key}:v1",
        "legacy_key": None,
        "dish_name": name,
        "aliases": [],
        "category": category,
        "meal_family": family,
        "sub_family": sub,
        "cuisine_region": region,
        "staple_type": staple,
        "protein_types": proteins,
        "serving_style": style,
        "meal_periods": periods,
        "delivery_fit": "unknown",
        "price_band": "unknown",
        "nature": "unknown",
        "seasonal_solar_terms": ["all_season"],
        "source_url": url,
        "source_type": "other_reviewed",
        "source_checked_at": CHECKED_AT,
        "nutrition_source_url": None,
        "nutrition_basis": None,
        "review_status": "draft",
        "reviewed_by": None,
        "reviewed_at": None,
        "review_notes": (
            "来源核验：美食天下公开菜谱页，作为菜名/做法存在性的候选发现来源；"
            "不把社区食谱当作商户菜单、价格、配送或营养证明。" + note
        ),
        "is_active": True,
        "catalog_version": 1,
        "taxonomy_version": 1,
        "forbidden_tags": [],
        "energy_kcal_min_per_person": energy[0],
        "energy_kcal_max_per_person": energy[1],
        "nutrition_note": "待按实际菜单份量复核；当前不作精确营养或功效承诺。",
        "order_tips": [],
        "high_protein": any(
            p in {"poultry", "pork", "beef", "lamb", "fish", "crustacean", "mollusk"}
            for p in proteins
        ),
        "anchor_food": anchor,
        "continuity_score": score,
    }


I = ["lunch", "dinner"]
ID = ["lunch", "dinner", "late_night"]
B = ["breakfast", "lunch", "dinner"]

# (key,name,category,family,sub,region,staple,proteins,style,periods,anchor,score,(min,max),url,note)
BATCH = [
    ("roast-pork-rib", "烤猪排", "烤肉", "single_dish", "stewed_dish", "cn_national", "none", ["pork"], "individual", I, "红烧肉", 76, (480, 820), "https://home.meishichina.com/recipe-667343.html", "猪排菜名和烹调方向明确，商户份量待审核。"),
    ("shiitake-sauce-noodle", "香菇酱拌面", "拌面", "noodle_meal", "dry_noodle", "cn_national", "wheat_noodle", ["soy"], "individual", I, "炸酱面", 82, (420, 720), "https://home.meishichina.com/recipe-667338.html", "面与菌菇结构接近现有面食，酱料盐油待审核。"),
    ("ginger-fish-slices", "子姜鱼片", "鱼片菜", "single_dish", "stir_fry", "cn_sichuan", "none", ["fish"], "individual", I, "清蒸鱼＋时蔬＋杂粮饭", 78, (360, 680), "https://home.meishichina.com/recipe-666854.html", "鱼片菜名和做法来源明确，辣度与鱼种待审核。"),
    ("poached-red-shrimp", "白灼阿根廷红虾", "白灼海鲜", "single_dish", "steamed_dish", "cn_national", "none", ["crustacean"], "individual", I, "虾仁滑蛋饭配时蔬", 80, (260, 520), "https://home.meishichina.com/recipe-667334.html", "虾类过敏原和商户可得性待审核。"),
    ("salt-pepper-lamb-ribs", "椒盐羊排", "羊肉菜", "single_dish", "stir_fry", "cn_northwest", "none", ["lamb"], "individual", I, "羊肉汤", 76, (520, 900), "https://home.meishichina.com/recipe-666852.html", "羊排结构可作为烤肉扩展，油盐与份量待审核。"),
    ("cold-beef-tongue", "白切牛舌", "牛肉冷盘", "single_dish", "cold_dish", "cn_national", "none", ["beef"], "individual", I, "清汤牛肉面", 72, (300, 600), "https://home.meishichina.com/recipe-666848.html", "冷盘存在性明确，是否适合日常外卖待审核。"),
    ("garlic-loofah-vermicelli-pot", "蒜蓉丝瓜粉丝煲", "粉丝煲", "single_dish", "steamed_dish", "cn_national", "rice_noodle", ["none"], "individual", I, "香煎豆腐杂蔬饭", 80, (260, 520), "https://home.meishichina.com/recipe-666847.html", "粉丝和蔬菜结构接近现有清淡菜，配送形态待审核。"),
    ("braised-chicken-feet", "卤鸡爪", "卤味", "single_dish", "stewed_dish", "cn_national", "none", ["poultry"], "individual", ID, "鸡肉时蔬饭", 74, (320, 650), "https://home.meishichina.com/recipe-667330.html", "卤味存在性明确，骨头和可食份量待审核。"),
    ("bamboo-shoot-red-braised-pork", "笋干红烧肉", "红烧肉", "single_dish", "stewed_dish", "cn_jiangzhe", "none", ["pork"], "individual", I, "红烧肉", 86, (560, 980), "https://home.meishichina.com/recipe-667326.html", "与现有红烧肉锚点高度连续，笋干供应和盐分待审核。"),
    ("fresh-shrimp-wonton", "鲜虾馄饨", "馄饨", "dumpling_bun", "wonton", "cn_jiangzhe", "dumpling_wrapper", ["crustacean"], "individual", B, "鲜虾蔬菜馄饨", 88, (320, 620), "https://home.meishichina.com/recipe-667323.html", "虾类过敏原与商户份量待审核。"),
    ("steamed-beef-tendon", "粉蒸板筋肉", "粉蒸肉", "single_dish", "steamed_dish", "cn_national", "whole_grain", ["pork"], "individual", I, "清蒸狮子头＋双份时蔬＋米饭", 74, (500, 860), "https://home.meishichina.com/recipe-666841.html", "粉蒸结构与现有蒸菜连续，具体部位待内容审核。"),
    ("crab-stick-scrambled-egg", "蟹柳滑蛋", "滑蛋菜", "single_dish", "stir_fry", "cn_national", "none", ["crustacean", "egg"], "individual", I, "番茄滑蛋牛肉饭", 82, (320, 620), "https://home.meishichina.com/recipe-667317.html", "蛋和海鲜结构明确，过敏原与份量待审核。"),
    ("chili-taro", "剁椒芋仔", "芋头菜", "single_dish", "steamed_dish", "cn_hunan", "tuber", ["none"], "individual", I, "香煎豆腐杂蔬饭", 74, (260, 520), "https://home.meishichina.com/recipe-666840.html", "芋头主食替代性和辣度待审核。"),
    ("scallion-shredded-chicken", "葱油手撕鸡", "手撕鸡", "single_dish", "cold_dish", "cn_cantonese", "none", ["poultry"], "individual", I, "海南鸡饭配青菜", 84, (380, 700), "https://home.meishichina.com/recipe-666820.html", "鸡肉冷盘与现有鸡肉饭连续，油量待审核。"),
    ("salt-pepper-chicken-thigh", "椒盐鸡腿", "鸡腿菜", "single_dish", "stir_fry", "cn_national", "none", ["poultry"], "individual", I, "鸡腿肉蔬菜糙米饭", 82, (450, 820), "https://home.meishichina.com/recipe-666849.html", "鸡腿结构明确，油炸/煎制方式待审核。"),
    ("cold-king-oyster-mushroom", "凉拌杏鲍菇", "凉拌菌菇", "single_dish", "cold_dish", "cn_national", "none", ["none"], "individual", I, "鸡肉蔬菜沙拉配玉米", 78, (180, 420), "https://home.meishichina.com/recipe-667290.html", "清淡凉菜与现有蔬菜结构连续，调味待审核。"),
    ("zucchini-egg-steamed-dumpling", "西葫芦鸡蛋蒸饺", "蒸饺", "dumpling_bun", "dumpling", "cn_national", "dumpling_wrapper", ["egg"], "individual", B, "北方手工饺子", 84, (360, 680), "https://home.meishichina.com/recipe-667284.html", "蒸饺存在性明确，蛋类过敏原待审核。"),
    ("radish-meat-gravy", "肉汁白萝卜", "萝卜菜", "single_dish", "stewed_dish", "cn_national", "none", ["pork"], "individual", I, "肉末茄子饭配青菜", 76, (260, 560), "https://home.meishichina.com/recipe-666817.html", "肉汁和萝卜结构接近家常炖菜，盐分待审核。"),
    ("spicy-tofu-lowcal-pot", "辣豆腐低卡锅", "豆腐锅", "hotpot_grill", "hotpot", "cn_sichuan", "none", ["soy"], "either", ID, "菌汤火锅＋豆腐蔬菜拼盘＋主食", 80, (380, 760), "https://home.meishichina.com/recipe-666815.html", "锅物适合按人数调整，辣度和份量待审核。"),
    ("chive-fish-dumpling", "韭菜佃鱼饺子", "鱼肉饺子", "dumpling_bun", "dumpling", "cn_fujian", "dumpling_wrapper", ["fish"], "individual", I, "三鲜水饺", 80, (380, 720), "https://home.meishichina.com/recipe-666814.html", "鱼肉饺子与现有水饺连续，鱼种待审核。"),
    ("scallion-beef-dumpling", "沙葱牛肉饺子", "牛肉饺子", "dumpling_bun", "dumpling", "cn_northwest", "dumpling_wrapper", ["beef"], "individual", I, "三鲜水饺", 84, (400, 760), "https://home.meishichina.com/recipe-666813.html", "牛肉饺子存在性明确，地域食材供应待审核。"),
    ("chive-fish-spring-roll", "韭菜佃鱼春卷", "鱼肉春卷", "wrap_light_meal", "wrap", "cn_fujian", "wheat_bread", ["fish"], "individual", ["lunch", "snack"], "上海春卷", 78, (320, 650), "https://home.meishichina.com/recipe-666812.html", "春卷结构连续，油炸方式和鱼种待审核。"),
    ("sesame-rice-noodle", "麻酱拌米粉", "拌米粉", "noodle_meal", "dry_noodle", "cn_national", "rice_noodle", ["soy"], "individual", I, "三鲜米线配青菜", 80, (400, 720), "https://home.meishichina.com/recipe-667251.html", "米粉结构与现有米线连续，芝麻过敏原待审核。"),
    ("black-pepper-beef-rib", "口蘑黑椒牛仔骨", "黑椒牛肉", "single_dish", "stir_fry", "cn_national", "none", ["beef"], "individual", I, "黑椒牛柳饭配彩椒", 84, (500, 900), "https://home.meishichina.com/recipe-666811.html", "牛肉与菌菇结构明确，部位和油量待审核。"),
    ("chive-pork-shrimp-dumpling", "韭菜猪肉虾仁饺子", "三鲜饺子", "dumpling_bun", "dumpling", "cn_national", "dumpling_wrapper", ["pork", "crustacean"], "individual", I, "三鲜水饺", 88, (420, 800), "https://home.meishichina.com/recipe-667240.html", "虾类过敏原与每份数量待审核。"),
    ("shacha-radish-beef-ball", "沙茶白萝卜牛肉丸", "牛肉丸", "single_dish", "stewed_dish", "cn_cantonese", "none", ["beef"], "individual", I, "番茄牛腩锅＋凉热双蔬＋主食", 80, (360, 700), "https://home.meishichina.com/recipe-666790.html", "牛肉丸与汤锅结构连续，沙茶盐分待审核。"),
    ("cold-asparagus-lettuce", "凉拌龙须菜", "凉拌蔬菜", "single_dish", "cold_dish", "cn_national", "none", ["none"], "individual", I, "鸡肉蔬菜沙拉配玉米", 76, (160, 380), "https://home.meishichina.com/recipe-667233.html", "凉菜存在性明确，食材名称和供应范围待审核。"),
    ("pepper-braised-yellow-fish", "线椒焖黄骨鱼", "焖鱼", "single_dish", "stewed_dish", "cn_hunan", "none", ["fish"], "individual", I, "清蒸鱼＋时蔬＋杂粮饭", 82, (380, 760), "https://home.meishichina.com/recipe-666774.html", "鱼类焖制与现有蒸鱼连续，辣度待审核。"),
    ("potato-pork-glass-noodle", "土豆五花肉炖粉条", "炖粉条", "single_dish", "stewed_dish", "cn_northeast", "rice_noodle", ["pork"], "individual", I, "大盘鸡小份＋拌青菜＋面或米饭", 82, (520, 940), "https://home.meishichina.com/recipe-666764.html", "土豆、猪肉、粉条结构完整，份量待审核。"),
    ("pork-belly-bamboo-stir-fry", "五花肉炒翡翠竹", "五花肉小炒", "single_dish", "stir_fry", "cn_national", "none", ["pork"], "individual", I, "肉末茄子饭配青菜", 78, (480, 860), "https://home.meishichina.com/recipe-667210.html", "家常小炒与现有猪肉菜连续，食材供应待审核。"),
    ("pork-ear-chive-bulb", "荞头炒猪耳朵", "猪耳朵小炒", "single_dish", "stir_fry", "cn_cantonese", "none", ["pork"], "individual", I, "湘味小炒肉＋蒸蛋＋时蔬＋米饭", 74, (420, 780), "https://home.meishichina.com/recipe-666765.html", "猪耳口感特殊，商户常见度与适配性待审核。"),
    ("cold-lotus-root", "凉拌藕片", "凉拌藕片", "single_dish", "cold_dish", "cn_national", "none", ["none"], "individual", I, "鸡肉蔬菜沙拉配玉米", 82, (160, 380), "https://home.meishichina.com/recipe-667194.html", "常见凉菜，酸辣度和配送待审核。"),
    ("zongye-steamed-beef-rib", "粽叶蒸牛肋条", "蒸牛肉", "single_dish", "steamed_dish", "cn_national", "none", ["beef"], "individual", I, "清蒸鱼＋时蔬＋杂粮饭", 76, (520, 900), "https://home.meishichina.com/recipe-667197.html", "牛肋条蒸制存在性明确，节令属性不外推。"),
    ("stir-fried-duck-giblets", "爆炒鸭杂", "鸭杂小炒", "single_dish", "stir_fry", "cn_national", "none", ["poultry"], "individual", I, "铁板鸡肉＋彩椒洋葱＋米饭", 74, (380, 760), "https://home.meishichina.com/recipe-666763.html", "鸭杂供应和内脏接受度待审核。"),
    ("poached-okra-mushroom", "白灼秋葵绣球菇", "白灼蔬菜", "single_dish", "steamed_dish", "cn_national", "none", ["none"], "individual", I, "鸡肉蔬菜沙拉配玉米", 80, (140, 360), "https://home.meishichina.com/recipe-667181.html", "清淡蔬菜结构明确，菌菇名称待审核。"),
    ("sauce-tofu", "浇汁豆腐", "豆腐菜", "single_dish", "steamed_dish", "cn_national", "none", ["soy"], "individual", I, "香煎豆腐杂蔬饭", 84, (240, 520), "https://home.meishichina.com/recipe-666745.html", "豆腐锚点明确，酱汁盐油待审核。"),
    ("vinegar-cabbage", "醋溜白菜", "白菜小炒", "single_dish", "stir_fry", "cn_national", "none", ["none"], "individual", I, "什锦素烩菜＋蒸蛋＋杂粮饭", 82, (160, 380), "https://home.meishichina.com/recipe-667176.html", "常见蔬菜菜，酸度和配送待审核。"),
    ("taro-steamed-pork", "芋仔粉蒸肉", "粉蒸肉", "single_dish", "steamed_dish", "cn_hunan", "tuber", ["pork"], "individual", I, "清蒸狮子头＋双份时蔬＋米饭", 80, (520, 940), "https://home.meishichina.com/recipe-666741.html", "芋头和猪肉结构清晰，份量待审核。"),
    ("garlic-chive-tofu-skin", "蒜黄炒腐竹", "腐竹小炒", "single_dish", "stir_fry", "cn_national", "none", ["soy"], "individual", I, "香煎豆腐杂蔬饭", 80, (260, 520), "https://home.meishichina.com/recipe-667159.html", "豆制品结构与现有豆腐菜连续，油量待审核。"),
    ("potato-braised-duck", "土豆焖鸭", "焖鸭", "single_dish", "stewed_dish", "cn_national", "tuber", ["poultry"], "individual", I, "大盘鸡小份＋拌青菜＋面或米饭", 78, (500, 900), "https://home.meishichina.com/recipe-666734.html", "禽肉加土豆结构接近现有焖炖菜，腥味和份量待审核。"),
    ("ham-egg-sandwich", "洪瑞珍鸡蛋火腿三明治", "火腿三明治", "wrap_light_meal", "sandwich", "east_asia", "wheat_bread", ["pork", "egg"], "individual", B, "鸡蛋蔬菜卷配玉米", 80, (360, 680), "https://home.meishichina.com/recipe-667147.html", "早餐三明治结构明确，品牌名和商户可得性待审核。"),
    ("yam-pearl-meatball", "山药珍珠丸子", "珍珠丸子", "single_dish", "steamed_dish", "cn_national", "whole_grain", ["pork"], "shared", I, "清蒸狮子头＋双份时蔬＋米饭", 80, (500, 900), "https://home.meishichina.com/recipe-667143.html", "共享蒸菜结构明确，人数份量待审核。"),
    ("cola-pork", "可乐梅花肉", "梅花肉", "single_dish", "stewed_dish", "cn_national", "none", ["pork"], "individual", I, "红烧肉", 78, (520, 900), "https://home.meishichina.com/recipe-665440.html", "与红烧肉同属炖煮结构，不外推为健康属性。"),
    ("perilla-braised-chicken", "紫苏焗鸡", "焗鸡", "single_dish", "stewed_dish", "cn_cantonese", "none", ["poultry"], "individual", I, "海南鸡饭配青菜", 80, (460, 820), "https://home.meishichina.com/recipe-666137.html", "鸡肉焗制与现有鸡肉饭连续，紫苏风味待审核。"),
    ("radish-adzuki-pork-bone-soup", "沙葛赤小豆大骨汤", "大骨汤", "soup_meal", "stew_soup_set", "cn_cantonese", "none", ["pork", "legume"], "shared", I, "莲藕排骨汤配时蔬饭", 78, (300, 620), "https://home.meishichina.com/recipe-666723.html", "汤类结构与现有排骨汤连续，不外推祛湿功效。"),
    ("curry-potato-minced-pork", "咖喱土豆肉沫", "咖喱菜", "rice_meal", "curry_rice", "cn_national", "rice", ["pork"], "individual", I, "咖喱鸡肉饭配蔬菜", 86, (520, 920), "https://home.meishichina.com/recipe-666724.html", "咖喱和土豆肉沫与现有咖喱饭连续，辣度待审核。"),
    ("scallion-oil-noodle", "葱油面", "葱油面", "noodle_meal", "dry_noodle", "cn_jiangzhe", "wheat_noodle", ["none"], "individual", B, "炸酱面", 84, (360, 660), "https://home.meishichina.com/recipe-667114.html", "常见面食，葱油盐分和配送待审核。"),
    ("dried-shrimp-winter-melon-soup", "海米冬瓜汤", "冬瓜汤", "soup_meal", "light_soup_set", "cn_national", "none", ["crustacean"], "individual", I, "冬瓜虾仁汤配杂粮饭", 84, (180, 420), "https://home.meishichina.com/recipe-667116.html", "冬瓜和海鲜结构与现有汤餐连续，过敏原待审核。"),
    ("shiitake-rib-braised-rice", "口蘑排骨焖饭", "排骨焖饭", "rice_meal", "braised_rice", "cn_national", "rice", ["pork"], "individual", I, "香菇鸡肉焖饭", 88, (560, 980), "https://home.meishichina.com/recipe-666142.html", "焖饭锚点明确，菌菇和排骨份量待审核。"),
    ("pork-trotter-braised-taro", "猪脚焖芋仔", "猪脚焖菜", "single_dish", "stewed_dish", "cn_national", "tuber", ["pork"], "shared", I, "砂锅鸡煲＋双份青菜＋米饭", 76, (650, 1150), "https://home.meishichina.com/recipe-666199.html", "共享炖菜结构明确，骨头和可食份量待审核。"),
    ("green-pepper-black-fungus-pork", "青椒木耳炒肉", "青椒炒肉", "single_dish", "stir_fry", "cn_national", "none", ["pork"], "individual", I, "肉末茄子饭配青菜", 84, (420, 780), "https://home.meishichina.com/recipe-666684.html", "家常小炒与现有猪肉菜连续，辣度待审核。"),
    ("shrimp-paste-beef-roll", "虾滑肥牛卷", "肥牛火锅", "hotpot_grill", "hotpot", "cn_national", "none", ["crustacean", "beef"], "either", ID, "清汤牛肉锅＋菌菇蔬菜拼盘＋主食", 86, (520, 980), "https://home.meishichina.com/recipe-666218.html", "锅物和双蛋白结构明确，海鲜/牛肉过敏原待审核。"),
]


def main() -> int:
    rows = json.loads(SEED.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("external seed 顶层必须是 list")
    existing = {item.get("catalog_key") for item in rows if isinstance(item, dict)}
    added = 0
    for values in BATCH:
        item = row(*values)
        if item["catalog_key"] in existing:
            continue
        rows.append(item)
        existing.add(item["catalog_key"])
        added += 1
    SEED.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"candidate_batch5_ok added={added} total={len(rows)} status=draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
