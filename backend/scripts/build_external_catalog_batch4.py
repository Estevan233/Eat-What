"""Append 52 recipe-index backed external candidates, all kept as draft.

The public recipe index proves dish-name/recipe existence only. It does not
prove live merchant inventory, price, delivery or nutrition; those facts stay
unknown until menu/content review. The script is deterministic and idempotent.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "backend" / "data" / "external_dining_seed.json"
CHECKED_AT = "2026-08-31T23:20:00+08:00"


def row(key, name, category, family, sub, region, staple, proteins, style, periods, anchor, score, energy, url, note):
    return {
        "catalog_key": f"external:batch4-{key}:v1", "legacy_key": None,
        "dish_name": name, "aliases": [], "category": category,
        "meal_family": family, "sub_family": sub, "cuisine_region": region,
        "staple_type": staple, "protein_types": proteins,
        "serving_style": style, "meal_periods": periods,
        "delivery_fit": "unknown", "price_band": "unknown", "nature": "unknown",
        "seasonal_solar_terms": ["all_season"], "source_url": url,
        "source_type": "other_reviewed", "source_checked_at": CHECKED_AT,
        "nutrition_source_url": None, "nutrition_basis": None,
        "review_status": "draft", "reviewed_by": None, "reviewed_at": None,
        "review_notes": ("来源核验：下厨房公开食谱页，作为菜名/做法存在性的候选发现来源；"
                         "不把社区食谱当作商户菜单、价格、配送或营养证明。" + note),
        "is_active": True, "catalog_version": 1, "taxonomy_version": 1,
        "forbidden_tags": [], "energy_kcal_min_per_person": energy[0],
        "energy_kcal_max_per_person": energy[1],
        "nutrition_note": "待按实际菜单份量复核；当前不作精确营养或功效承诺。",
        "order_tips": [], "high_protein": any(p in {
            "poultry", "pork", "beef", "lamb", "fish", "crustacean", "mollusk"
        } for p in proteins), "anchor_food": anchor, "continuity_score": score,
    }


I = ["lunch", "dinner"]
ID = ["lunch", "dinner", "late_night"]
BR = ["breakfast", "lunch"]
B = ["breakfast", "lunch", "dinner"]

# (key,name,category,family,sub,region,staple,proteins,style,periods,anchor,score,(min,max),url,note)
BATCH = [
    ("spare-rib-claypot-rice", "豉汁排骨煲仔饭", "广式煲仔饭", "rice_meal", "claypot_rice", "cn_cantonese", "rice", ["pork"], "individual", I, "腊味煲仔饭配青菜", 84, (520, 860), "https://www.xiachufang.com/recipe/107138573/", "来源菜名明确包含排骨煲仔饭；酱汁、份量和配送待审核。"),
    ("japanese-beef-rice", "日式肥牛饭", "牛肉盖饭", "rice_meal", "rice_bowl", "east_asia", "rice", ["beef"], "individual", I, "黑椒牛柳饭配彩椒", 82, (520, 820), "https://www.xiachufang.com/recipe/106250012/", "来源公开食谱列出日式肥牛饭；商户菜单存在性待核验。"),
    ("lettuce-beef-mixed-rice", "生菜牛肉拌饭", "牛肉拌饭", "rice_meal", "rice_bowl", "cn_national", "rice", ["beef"], "individual", I, "韩式杂蔬拌饭", 84, (480, 780), "https://www.xiachufang.com/recipe/107148148/", "来源公开食谱列出生菜牛肉拌饭；配菜和份量待审核。"),
    ("beef-claypot-rice", "牛肉焖饭", "牛肉焖饭", "rice_meal", "braised_rice", "cn_national", "rice", ["beef"], "individual", I, "香菇鸡肉焖饭", 80, (500, 840), "https://www.xiachufang.com/recipe/107031126/", "来源公开食谱列出牛肉焖饭；具体配菜待审核。"),
    ("teriyaki-chicken-thigh-rice", "照烧鸡腿饭", "鸡腿盖饭", "rice_meal", "rice_bowl", "east_asia", "rice", ["poultry"], "individual", I, "鸡腿肉蔬菜糙米饭", 86, (520, 820), "https://www.xiachufang.com/recipe/104126605/", "来源公开食谱列出照烧鸡腿饭；甜咸度和配菜待审核。"),
    ("cola-chicken-rice", "可乐鸡腿饭", "鸡腿盖饭", "rice_meal", "rice_bowl", "cn_national", "rice", ["poultry"], "individual", I, "鸡肉时蔬饭", 76, (540, 860), "https://www.xiachufang.com/recipe/107328208/", "来源公开食谱列出可乐鸡腿饭；不把名称外推为健康属性。"),
    ("yangzhou-fried-rice", "扬州炒饭", "什锦炒饭", "rice_meal", "fried_rice", "cn_jiangzhe", "rice", ["egg", "pork"], "individual", I, "虾仁滑蛋饭配时蔬", 86, (450, 760), "https://www.xiachufang.com/recipe/107255945/", "来源公开食谱明确列出扬州炒饭；配料比例待审核。"),
    ("soy-sauce-fried-rice", "酱油炒饭", "家常炒饭", "rice_meal", "fried_rice", "cn_national", "rice", ["egg"], "individual", I, "蛋炒饭", 78, (400, 700), "https://www.xiachufang.com/recipe/106457495/", "来源公开食谱明确列出酱油炒饭；盐油用量待审核。"),
    ("shrimp-fried-rice", "虾仁炒饭", "海鲜炒饭", "rice_meal", "fried_rice", "cn_national", "rice", ["crustacean", "egg"], "individual", I, "虾仁滑蛋饭配时蔬", 84, (430, 740), "https://www.xiachufang.com/recipe/106513946/", "来源公开食谱明确列出虾仁炒饭；过敏原和份量待审核。"),
    ("seaweed-fried-rice", "紫菜炒饭", "家常炒饭", "rice_meal", "fried_rice", "cn_national", "rice", ["egg"], "individual", I, "蛋炒饭", 74, (380, 680), "https://www.xiachufang.com/recipe/106148662/", "来源公开食谱明确列出紫菜炒饭；食材搭配待审核。"),
    ("tomato-egg-beef-rice", "番茄滑蛋牛肉饭", "牛肉盖饭", "rice_meal", "rice_bowl", "cn_national", "rice", ["beef", "egg"], "individual", I, "番茄牛腩粉", 85, (500, 820), "https://www.xiachufang.com/recipe/106962346/", "来源公开食谱明确列出番茄滑蛋牛肉饭；熟度和份量待审核。"),
    ("potato-beef-mixed-rice", "土豆肥牛拌饭", "牛肉拌饭", "rice_meal", "rice_bowl", "cn_national", "rice", ["beef"], "individual", I, "韩式杂蔬拌饭", 82, (520, 860), "https://www.xiachufang.com/recipe/104220666/", "来源公开食谱明确列出土豆肥牛拌饭；配菜和油盐待审核。"),
    ("shrimp-wonton-noodle", "广式鲜虾云吞面", "云吞面", "dumpling_bun", "wonton", "cn_cantonese", "wheat_noodle", ["crustacean"], "individual", I, "云吞面配白灼菜", 88, (420, 720), "https://www.xiachufang.com/recipe/107411484/", "来源公开食谱明确列出鲜虾云吞面；虾类过敏提示待审核。"),
    ("kunming-crossing-noodle", "老昆明过桥米线", "云南米线", "noodle_meal", "rice_noodle_soup", "cn_yunnan_guizhou", "rice_noodle", ["poultry"], "individual", I, "三鲜米线配青菜", 88, (420, 760), "https://www.xiachufang.com/recipe/106145818/", "来源公开食谱明确列出过桥米线；汤底和生熟分装待审核。"),
    ("kunming-small-pot-noodle", "小锅米线", "云南米线", "noodle_meal", "rice_noodle_soup", "cn_yunnan_guizhou", "rice_noodle", ["pork"], "individual", I, "三鲜米线配青菜", 84, (400, 700), "https://www.xiachufang.com/recipe/104365244/", "来源公开食谱明确列出小锅米线；配菜和辣度待审核。"),
    ("liuzhou-luosifen", "柳州螺蛳粉", "地方米粉", "noodle_meal", "rice_noodle_soup", "cn_national", "rice_noodle", ["none"], "individual", ID, "酸汤鱼片粉", 84, (450, 780), "https://www.xiachufang.com/recipe/1046417/", "来源公开食谱明确列出柳州螺蛳粉；汤底气味和配送待审核。"),
    ("guilin-rice-noodle", "桂林米粉", "地方米粉", "noodle_meal", "rice_noodle_soup", "cn_national", "rice_noodle", ["pork"], "individual", B, "三鲜米线配青菜", 86, (400, 720), "https://www.xiachufang.com/recipe/1078918/", "来源公开食谱明确列出桂林米粉；卤水、配菜待审核。"),
    ("chengdu-dandan-noodle", "成都担担面", "川味面食", "noodle_meal", "dry_noodle", "cn_sichuan", "wheat_noodle", ["pork"], "individual", ID, "重庆小面", 86, (430, 740), "https://www.xiachufang.com/recipe/102241978/", "来源公开食谱明确列出成都担担面；辣度和花生过敏提示待审核。"),
    ("beijing-fried-sauce-noodle", "老北京炸酱面", "京味面食", "noodle_meal", "dry_noodle", "cn_beijing_tianjin", "wheat_noodle", ["pork"], "individual", I, "炸酱面", 88, (480, 800), "https://www.xiachufang.com/recipe/104623627/", "来源公开食谱明确列出老北京炸酱面；酱料盐分待审核。"),
    ("chongqing-wanza-noodle", "重庆豌杂面", "川味面食", "noodle_meal", "dry_noodle", "cn_sichuan", "wheat_noodle", ["pork", "legume"], "individual", ID, "重庆小面", 84, (480, 820), "https://www.xiachufang.com/recipe/104511393/", "来源公开食谱明确列出重庆豌杂面；辣度和油量待审核。"),
    ("braised-beef-noodle", "红烧牛肉面", "牛肉面", "noodle_meal", "noodle_soup", "cn_national", "wheat_noodle", ["beef"], "individual", I, "清汤牛肉面", 88, (520, 860), "https://www.xiachufang.com/recipe/104693816/", "来源公开食谱明确列出红烧牛肉面；汤底盐分待审核。"),
    ("oil-splashed-noodle", "油泼面", "陕西面食", "noodle_meal", "dry_noodle", "cn_northwest", "wheat_noodle", ["none"], "individual", I, "蓝田裤带面", 82, (430, 760), "https://www.xiachufang.com/recipe/104129250/", "来源公开食谱明确列出油泼面；油辣度待审核。"),
    ("egg-beef-vegetable-noodle", "鸡蛋牛肉青菜面", "家常汤面", "noodle_meal", "noodle_soup", "cn_national", "wheat_noodle", ["beef", "egg"], "individual", B, "清汤牛肉面", 80, (420, 720), "https://www.xiachufang.com/recipe/107378330/", "来源公开食谱明确列出鸡蛋牛肉青菜面；配菜比例待审核。"),
    ("clear-braised-beef-noodle", "清炖牛肉面", "牛肉面", "noodle_meal", "noodle_soup", "cn_national", "wheat_noodle", ["beef"], "individual", I, "清汤牛肉面", 84, (480, 820), "https://www.xiachufang.com/recipe/103782817/", "来源公开食谱明确列出清炖牛肉面；清炖汤底与份量待审核。"),
    ("cabbage-pork-dumpling", "白菜猪肉水饺", "手工水饺", "dumpling_bun", "dumpling", "cn_national", "dumpling_wrapper", ["pork"], "individual", I, "韭菜猪肉水饺", 86, (430, 760), "https://www.xiachufang.com/recipe/104225259/", "来源公开食谱明确列出白菜猪肉水饺；每份数量待审核。"),
    ("three-fresh-dumpling", "三鲜水饺", "手工水饺", "dumpling_bun", "dumpling", "cn_national", "dumpling_wrapper", ["pork", "crustacean", "egg"], "individual", I, "鲜虾蔬菜馄饨", 88, (420, 760), "https://www.xiachufang.com/recipe/103815482/", "来源公开食谱明确列出三鲜水饺；海鲜/蛋类过敏提示待审核。"),
    ("sauce-pork-xiaolongbao", "酱肉小笼包", "小笼包", "dumpling_bun", "steamed_bun", "cn_jiangzhe", "wheat_bread", ["pork"], "individual", BR, "小笼包", 82, (380, 680), "https://www.xiachufang.com/recipe/107415877/", "来源公开食谱明确列出酱肉小笼包；汤汁和份量待审核。"),
    ("fresh-pork-xiaolongbao", "鲜肉小笼包", "小笼包", "dumpling_bun", "steamed_bun", "cn_jiangzhe", "wheat_bread", ["pork"], "individual", BR, "小笼包", 84, (360, 660), "https://www.xiachufang.com/recipe/106789387/", "来源公开食谱明确列出鲜肉小笼包；汤汁和份量待审核。"),
    ("sticky-rice-shaomai", "糯米烧麦", "烧麦", "dumpling_bun", "dim_sum", "cn_national", "dumpling_wrapper", ["pork"], "individual", BR, "蒸点拼盘＋粥＋青菜", 82, (360, 680), "https://www.xiachufang.com/recipe/1040364/", "来源公开食谱明确列出糯米烧麦；糯米份量待审核。"),
    ("beef-onion-shaomai", "牛肉洋葱烧麦", "烧麦", "dumpling_bun", "dim_sum", "cn_national", "dumpling_wrapper", ["beef"], "individual", BR, "蒸点拼盘＋粥＋青菜", 80, (380, 700), "https://www.xiachufang.com/recipe/102772998/", "来源公开食谱明确列出牛肉洋葱烧麦；洋葱配比待审核。"),
    ("three-fresh-potsticker", "三鲜锅贴", "锅贴", "dumpling_bun", "dumpling", "cn_national", "dumpling_wrapper", ["pork", "crustacean", "egg"], "individual", I, "家常蛋饺", 82, (420, 760), "https://www.xiachufang.com/recipe/46509/", "来源公开食谱明确列出三鲜锅贴；海鲜/蛋类过敏提示待审核。"),
    ("fresh-pork-potsticker", "鲜肉锅贴", "锅贴", "dumpling_bun", "dumpling", "cn_national", "dumpling_wrapper", ["pork"], "individual", I, "家常蛋饺", 82, (400, 720), "https://www.xiachufang.com/recipe/104420280/", "来源公开食谱明确列出鲜肉锅贴；煎制油量待审核。"),
    ("fresh-pork-wonton", "鲜肉小馄饨", "馄饨", "dumpling_bun", "wonton", "cn_jiangzhe", "dumpling_wrapper", ["pork"], "individual", B, "鲜虾蔬菜馄饨", 84, (330, 620), "https://www.xiachufang.com/recipe/104680926/", "来源公开食谱明确列出鲜肉小馄饨；汤底盐分待审核。"),
    ("sour-soup-wonton", "酸汤馄饨", "馄饨", "dumpling_bun", "wonton", "cn_national", "dumpling_wrapper", ["pork"], "individual", ID, "鲜虾蔬菜馄饨", 80, (350, 680), "https://www.xiachufang.com/recipe/104186015/", "来源公开食谱明确列出酸汤馄饨；酸辣度和盐分待审核。"),
    ("century-egg-pork-congee", "皮蛋瘦肉粥", "粥品", "grain_congee", "congee", "cn_cantonese", "congee", ["pork", "egg"], "individual", B, "南瓜小米粥配蒸蛋", 88, (260, 520), "https://www.xiachufang.com/recipe/107383411/", "来源公开食谱明确列出皮蛋瘦肉粥；皮蛋/猪肉份量待审核。"),
    ("corn-pork-rib-soup", "玉米排骨汤", "排骨汤", "soup_meal", "stew_soup_set", "cn_national", "none", ["pork"], "individual", I, "莲藕排骨汤配时蔬饭", 84, (260, 520), "https://www.xiachufang.com/recipe/106405041/", "来源公开食谱明确列出玉米排骨汤；汤量和盐分待审核。"),
    ("winter-melon-rib-soup", "冬瓜排骨汤", "排骨汤", "soup_meal", "stew_soup_set", "cn_national", "none", ["pork"], "individual", I, "冬瓜虾仁汤配杂粮饭", 82, (220, 500), "https://www.xiachufang.com/recipe/104640281/", "来源公开食谱明确列出冬瓜排骨汤；汤量和盐分待审核。"),
    ("yam-pork-rib-soup", "山药排骨汤", "排骨汤", "soup_meal", "stew_soup_set", "cn_national", "none", ["pork"], "individual", I, "莲藕排骨汤配时蔬饭", 82, (240, 520), "https://www.xiachufang.com/recipe/107407712/", "来源公开食谱明确列出山药排骨汤；不外推滋补功效。"),
    ("lotus-root-rib-soup", "莲藕排骨汤", "排骨汤", "soup_meal", "stew_soup_set", "cn_national", "none", ["pork"], "individual", I, "莲藕排骨汤配时蔬饭", 86, (260, 540), "https://www.xiachufang.com/recipe/106855645/", "来源公开食谱明确列出莲藕排骨汤；汤量和盐分待审核。"),
    ("henan-pepper-soup", "河南胡辣汤", "地方汤食", "soup_meal", "light_soup_set", "cn_northwest", "wheat_bread", ["beef"], "individual", BR, "羊肉汤", 82, (300, 620), "https://www.xiachufang.com/recipe/104363257/", "来源公开食谱明确列出河南胡辣汤；辣度、盐分和配料待审核。"),
    ("tianjin-jianbing", "天津煎饼果子", "地方早餐", "wrap_light_meal", "wrap", "cn_beijing_tianjin", "wheat_bread", ["egg"], "individual", ["breakfast"], "鸡蛋蔬菜卷配玉米", 86, (380, 680), "https://www.xiachufang.com/recipe/104138431/", "来源公开食谱明确列出天津煎饼果子；脆片和酱料待审核。"),
    ("classic-roujiamo", "肉夹馍", "地方夹馍", "wrap_light_meal", "wrap", "cn_northwest", "wheat_bread", ["pork"], "individual", BR, "西安腊汁肉夹馍", 82, (450, 780), "https://www.xiachufang.com/recipe/104416332/", "来源公开食谱明确列出肉夹馍；与腊汁肉夹馍的差异待内容审核。"),
    ("scallion-hand-grab-cake", "葱香手抓饼", "地方面点", "wrap_light_meal", "wrap", "cn_national", "wheat_bread", ["none"], "individual", ["breakfast", "snack"], "鸡蛋蔬菜卷配玉米", 76, (330, 620), "https://www.xiachufang.com/recipe/104368514/", "来源公开食谱明确列出葱香手抓饼；油量和夹馅待审核。"),
    ("shanghai-spring-roll", "上海春卷", "地方小吃", "wrap_light_meal", "wrap", "cn_jiangzhe", "wheat_bread", ["pork"], "individual", ["lunch", "snack"], "鸡蛋蔬菜卷配玉米", 78, (300, 620), "https://www.xiachufang.com/recipe/104351309/", "来源公开食谱明确列出上海春卷；油炸方式和份量待审核。"),
    ("solo-mala-hotpot", "一人食火锅冒菜", "麻辣火锅", "hotpot_grill", "hotpot", "cn_sichuan", "none", ["soy", "pork"], "either", ID, "菌汤火锅＋豆腐蔬菜拼盘＋主食", 80, (450, 900), "https://www.xiachufang.com/recipe/106880837/", "来源公开食谱明确列出一人食火锅冒菜；商户份型和辣度待审核。"),
    ("red-sour-hotpot", "红酸汤火锅", "贵州火锅", "hotpot_grill", "hotpot", "cn_yunnan_guizhou", "none", ["fish"], "shared", I, "番茄牛腩锅＋凉热双蔬＋主食", 82, (650, 1200), "https://www.xiachufang.com/recipe/107676972/", "来源公开食谱明确列出红酸汤火锅；共享份量和鱼类选项待审核。"),
    ("home-style-hotpot", "家常火锅", "家庭火锅", "hotpot_grill", "hotpot", "cn_national", "none", ["soy", "pork"], "shared", I, "菌汤火锅＋豆腐蔬菜拼盘＋主食", 78, (700, 1300), "https://www.xiachufang.com/recipe/101757925/", "来源公开食谱明确列出家庭火锅；锅底、配菜和份量待审核。"),
    ("chongqing-grilled-fish", "重庆烤鱼", "烤鱼", "hotpot_grill", "grilled_share", "cn_sichuan", "none", ["fish"], "shared", I, "烤鱼小份＋双拼蔬菜＋主食", 86, (700, 1250), "https://www.xiachufang.com/recipe/104546492/", "来源公开食谱明确列出重庆烤鱼；鱼种、辣度和共享份量待审核。"),
    ("scallion-grilled-fish", "葱香烤鱼", "烤鱼", "hotpot_grill", "grilled_share", "cn_national", "none", ["fish"], "shared", I, "烤鱼小份＋双拼蔬菜＋主食", 80, (650, 1150), "https://www.xiachufang.com/recipe/104511180/", "来源公开食谱明确列出葱香烤鱼；鱼种、油量和共享份量待审核。"),
    ("home-style-barbecue", "家庭烧烤", "烧烤", "hotpot_grill", "grilled_share", "cn_national", "none", ["poultry", "pork"], "shared", ["dinner", "late_night"], "铁板鸡肉＋彩椒洋葱＋米饭", 74, (700, 1300), "https://www.xiachufang.com/recipe/104163935/", "来源公开食谱明确列出家庭烧烤；烤制品类和份量待菜单审核。"),
    ("mala-tang", "麻辣烫", "麻辣烫", "hotpot_grill", "hotpot", "cn_sichuan", "none", ["soy", "pork"], "either", ID, "菌汤火锅＋豆腐蔬菜拼盘＋主食", 82, (420, 950), "https://www.xiachufang.com/recipe/103955472/", "来源公开食谱明确列出麻辣烫；商户自选配菜、辣度和汤底待审核。"),
    ("mala-ban", "麻辣拌", "麻辣拌", "hotpot_grill", "hotpot", "cn_northeast", "none", ["soy", "pork"], "either", ID, "菌汤火锅＋豆腐蔬菜拼盘＋主食", 78, (380, 850), "https://www.xiachufang.com/recipe/105897606/", "来源公开食谱明确列出麻辣拌；商户自选配菜和辣度待审核。"),
]


def main() -> int:
    rows = json.loads(SEED.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("external seed 顶层必须是 list")
    existing = {x.get("catalog_key") for x in rows if isinstance(x, dict)}
    added = 0
    for values in BATCH:
        item = row(*values)
        if item["catalog_key"] in existing:
            continue
        rows.append(item)
        existing.add(item["catalog_key"])
        added += 1
    SEED.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"candidate_batch4_ok added={added} total={len(rows)} status=draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
