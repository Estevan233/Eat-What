"""Append a conservative source-backed candidate batch.

The source page is a government-hosted cultural-heritage article. We only use
names explicitly present in that page; combinations that require menu/portion
judgement stay in draft. This script is deterministic and idempotent.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "external_dining_seed.json"
SOURCE_URL = "https://www.ihchina.cn/project_details/10278"
CHECKED_AT = "2026-08-31T00:00:00+08:00"


def _row(
    key: str,
    name: str,
    category: str,
    family: str,
    sub_family: str,
    region: str,
    staple: str,
    proteins: list[str],
    style: str,
    periods: list[str],
    delivery: str,
    price: str,
    anchor: str,
    score: int,
    energy: tuple[int, int],
    note: str,
) -> dict[str, object]:
    return {
        "catalog_key": f"external:batch1-{key}:v1",
        "legacy_key": None,
        "dish_name": name,
        "aliases": [],
        "category": category,
        "meal_family": family,
        "sub_family": sub_family,
        "cuisine_region": region,
        "staple_type": staple,
        "protein_types": proteins,
        "serving_style": style,
        "meal_periods": periods,
        "delivery_fit": delivery,
        "price_band": price,
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
            "来源核验：中国非遗网文章正文列举该名称；"
            "仅作候选发现依据，尚未完成菜单形态、营养和内容审核，不得进入线上推荐。"
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
        "high_protein": any(
            p in {"poultry", "pork", "beef", "lamb", "fish", "crustacean", "mollusk"}
            for p in proteins
        ),
        "anchor_food": anchor,
        "continuity_score": score,
    }


BATCH: list[dict[str, object]] = [
    _row("north-dumpling", "北方手工饺子", "手工饺子", "dumpling_bun", "dumpling", "cn_northwest", "dumpling_wrapper", ["pork"], "individual", ["lunch", "dinner"], "high", "budget", "韭菜猪肉水饺", 82, (450, 750), "页面明确列举北方饺子；手工是待审核的供应方式描述。"),
    _row("sweet-rice-ball", "传统元宵", "节令点心", "dumpling_bun", "dumpling", "cn_national", "dumpling_wrapper", ["none"], "individual", ["breakfast", "snack"], "medium", "budget", "红豆包子", 70, (260, 480), "页面列举南方元宵；节令供应需人工确认。"),
    _row("lamb-paomo", "西安羊肉泡馍", "地方汤食", "soup_meal", "stew_soup_set", "cn_northwest", "wheat_bread", ["lamb"], "individual", ["lunch", "dinner"], "medium", "standard", "羊肉汤", 84, (600, 900), "页面明确列举西安羊肉泡馍。"),
    _row("huai-an-tofu", "淮安豆腐", "传统豆制品", "single_dish", "stewed_dish", "cn_jiangzhe", "none", ["soy"], "individual", ["lunch", "dinner"], "high", "budget", "家常豆腐", 78, (180, 360), "页面列举淮安豆腐；具体做法不在本批推断。"),
    _row("kaifeng-tangbao", "开封灌汤包", "地方包点", "dumpling_bun", "dim_sum", "cn_national", "dumpling_wrapper", ["pork"], "individual", ["breakfast", "lunch"], "medium", "standard", "小笼包", 88, (380, 650), "页面列举开封灌汤包；汤汁配送风险待内容审核。"),
    _row("eighteen-street-mahua", "桂发祥十八街麻花", "传统面点", "snack_dessert", "snack", "cn_beijing_tianjin", "wheat_bread", ["none"], "individual", ["snack"], "high", "budget", "发糕", 74, (300, 550), "页面列举该名称；品牌/商标信息不复制。"),
    _row("wufangzhai-zongzi", "五芳斋粽子", "传统粽点", "snack_dessert", "snack", "cn_jiangzhe", "mixed", ["pork"], "individual", ["breakfast", "snack"], "high", "budget", "糯米鸡", 82, (350, 650), "页面列举五芳斋粽子；不复制品牌菜单。"),
    _row("nanxiang-xiaolong", "南翔小笼", "地方包点", "dumpling_bun", "dim_sum", "cn_jiangzhe", "dumpling_wrapper", ["pork"], "individual", ["breakfast", "lunch"], "medium", "standard", "小笼包", 90, (350, 600), "页面列举南翔小笼；与开封灌汤包的差异需人工复核。"),
    _row("hanzhong-mianpi", "汉中面皮", "地方面食", "noodle_meal", "dry_noodle", "cn_northwest", "wheat_noodle", ["none"], "individual", ["lunch", "dinner"], "high", "budget", "凉拌粉皮", 86, (380, 650), "页面列举汉中面皮。"),
    _row("ningxia-hand-noodle", "宁夏手擀面", "地方面食", "noodle_meal", "noodle_soup", "cn_northwest", "wheat_noodle", ["none"], "individual", ["lunch", "dinner"], "high", "budget", "阳春面", 84, (420, 700), "页面列举宁夏手擀面。"),
    _row("lantian-kudai", "蓝田裤带面", "地方面食", "noodle_meal", "dry_noodle", "cn_northwest", "wheat_noodle", ["none"], "individual", ["lunch", "dinner"], "high", "budget", "炸酱面", 82, (450, 750), "页面列举蓝田裤带面。"),
    _row("sichuan-tianshui", "四川甜水面", "地方面食", "noodle_meal", "dry_noodle", "cn_sichuan", "wheat_noodle", ["none"], "individual", ["lunch", "snack"], "high", "budget", "炸酱面", 80, (420, 700), "页面列举四川甜水面；甜辣口味待审核。"),
    _row("shaanxi-saozi", "陕西臊子面", "地方面食", "noodle_meal", "noodle_soup", "cn_northwest", "wheat_noodle", ["pork"], "individual", ["lunch", "dinner"], "medium", "standard", "牛肉面", 84, (500, 800), "页面列举陕西臊子面。"),
    _row("shanxi-heluo", "山西饸饹", "地方面食", "noodle_meal", "noodle_soup", "cn_northwest", "wheat_noodle", ["none"], "individual", ["lunch", "dinner"], "high", "budget", "牛肉面", 78, (430, 700), "页面列举山西饸饹。"),
    _row("wuhan-reganmian", "武汉热干面", "地方面食", "noodle_meal", "dry_noodle", "cn_national", "wheat_noodle", ["none"], "individual", ["breakfast", "lunch"], "high", "budget", "炸酱面", 86, (450, 700), "页面列举武汉热干面。"),
    _row("chongqing-xiaomian", "重庆小面", "地方面食", "noodle_meal", "dry_noodle", "cn_sichuan", "wheat_noodle", ["none"], "individual", ["breakfast", "lunch", "late_night"], "high", "budget", "酸辣粉", 88, (400, 680), "页面列举重庆小面。"),
    _row("suzhou-toutang", "苏州头汤面", "地方面食", "noodle_meal", "noodle_soup", "cn_jiangzhe", "wheat_noodle", ["pork"], "individual", ["breakfast", "lunch"], "medium", "standard", "阳春面", 83, (420, 700), "页面列举苏州头汤面。"),
    _row("hangzhou-pianerchuan", "杭州片儿川", "地方面食", "noodle_meal", "noodle_soup", "cn_jiangzhe", "wheat_noodle", ["pork"], "individual", ["lunch", "dinner"], "medium", "standard", "阳春面", 86, (500, 780), "页面列举杭州片儿川。"),
    _row("taiwan-village-beef-noodle", "眷村牛肉面", "地方面食", "noodle_meal", "noodle_soup", "east_asia", "wheat_noodle", ["beef"], "individual", ["lunch", "dinner"], "medium", "standard", "牛肉面", 88, (550, 850), "页面列举台湾眷村牛肉面。"),
    _row("guangzhou-bamboo-noodle", "广州竹升面", "地方面食", "noodle_meal", "noodle_soup", "cn_cantonese", "wheat_noodle", ["egg"], "individual", ["lunch", "dinner"], "high", "standard", "云吞面配白灼菜", 83, (420, 700), "页面列举广州竹升面。"),
    _row("xinjiang-naan", "新疆烤馕", "传统面点", "snack_dessert", "snack", "cn_northwest", "wheat_bread", ["none"], "individual", ["breakfast", "snack"], "high", "budget", "杂粮馒头", 80, (300, 600), "页面列举新疆烤馕。"),
    _row("hongkong-abalone-noodle", "香港虾籽捞面", "地方面食", "noodle_meal", "dry_noodle", "cn_cantonese", "wheat_noodle", ["crustacean"], "individual", ["lunch", "dinner"], "high", "standard", "云吞面配白灼菜", 86, (430, 720), "页面列举香港虾籽捞面；虾籽过敏提示待审核。"),
    _row("lanzhou-lamian", "兰州拉面", "地方面食", "noodle_meal", "noodle_soup", "cn_northwest", "wheat_noodle", ["beef"], "individual", ["breakfast", "lunch", "dinner"], "high", "budget", "牛肉面", 92, (500, 850), "页面列举兰州拉面。"),
    _row("xian-roujiamo", "西安腊汁肉夹馍", "地方小吃", "wrap_light_meal", "wrap", "cn_northwest", "wheat_bread", ["pork"], "individual", ["breakfast", "lunch"], "high", "budget", "牛肉蔬菜卷饼", 86, (450, 750), "页面列举西安腊汁肉夹馍。"),
    _row("egg-dumpling", "家常蛋饺", "传统年菜", "dumpling_bun", "dumpling", "cn_jiangzhe", "dumpling_wrapper", ["egg", "pork"], "individual", ["lunch", "dinner"], "medium", "standard", "韭菜猪肉水饺", 86, (400, 700), "页面以蛋饺为年菜例；馅料和份型待审核。"),
    _row("longyou-fagao", "龙游发糕", "地方糕点", "snack_dessert", "snack", "cn_jiangzhe", "wheat_bread", ["none"], "individual", ["breakfast", "snack"], "high", "budget", "发糕", 90, (280, 520), "页面列举龙游发糕。"),
    _row("tiantiao", "条头糕", "江南糕点", "snack_dessert", "snack", "cn_jiangzhe", "wheat_bread", ["none"], "individual", ["snack"], "high", "budget", "发糕", 86, (280, 520), "页面列举条头糕。"),
    _row("chongyang-gao", "重阳糕", "节令糕点", "snack_dessert", "snack", "cn_jiangzhe", "wheat_bread", ["nut_seed"], "individual", ["snack"], "high", "budget", "发糕", 83, (300, 560), "页面列举重阳糕。"),
    _row("huang-song-gao", "黄松糕", "江南糕点", "snack_dessert", "snack", "cn_jiangzhe", "wheat_bread", ["none"], "individual", ["snack"], "high", "budget", "发糕", 82, (280, 520), "页面列举黄松糕。"),
    _row("qing-tuan", "江南青团", "节令点心", "snack_dessert", "snack", "cn_jiangzhe", "wheat_bread", ["none"], "individual", ["breakfast", "snack"], "high", "budget", "红豆包子", 84, (280, 560), "页面列举青团。"),
    _row("honggui-guo", "闽南红龟粿", "地方糕点", "snack_dessert", "snack", "cn_fujian", "wheat_bread", ["none"], "individual", ["snack"], "high", "budget", "红豆包子", 84, (280, 560), "页面列举红龟粿。"),
    _row("shanghai-benbang", "上海本帮菜合餐", "本帮合菜", "shared_dishes", "regional_share", "cn_jiangzhe", "rice", ["pork"], "shared", ["lunch", "dinner"], "medium", "standard", "红烧肉", 86, (700, 1100), "页面将上海本帮菜列为传统烹饪技艺；具体菜单需内容审核。"),
    _row("beijing-roast-duck", "北京烤鸭共享餐", "地方名菜", "shared_dishes", "regional_share", "cn_beijing_tianjin", "wheat_bread", ["poultry"], "shared", ["lunch", "dinner"], "medium", "premium", "烧鹅", 90, (800, 1300), "页面列举北京烤鸭；共享份量和配送风险待审核。"),
    _row("yunnan-ham-platter", "云南火腿拼盘", "地方风味拼盘", "shared_dishes", "regional_share", "cn_yunnan_guizhou", "rice", ["pork"], "shared", ["lunch", "dinner"], "high", "premium", "蒸腊肉", 86, (600, 1000), "页面列举云南火腿；拼盘构成待审核。"),
    _row("new-year-dumpling-feast", "北方饺子团圆餐", "节俗合餐", "shared_dishes", "regional_share", "cn_northwest", "dumpling_wrapper", ["pork"], "shared", ["dinner"], "medium", "standard", "韭菜猪肉水饺", 92, (700, 1200), "页面说明北方年节饺子团圆语境；份量需审核。"),
    _row("meifudoufu-platter", "霉豆腐风味小菜拼盘", "传统发酵小菜", "shared_dishes", "regional_share", "cn_national", "rice", ["soy"], "shared", ["lunch", "dinner"], "high", "budget", "家常豆腐", 72, (350, 700), "页面列举霉豆腐；小菜拼盘为产品组合，待审核。"),
    _row("zaobodou-share", "糟钵斗风味合餐", "地方风味合菜", "shared_dishes", "regional_share", "cn_fujian", "rice", ["fish"], "shared", ["lunch", "dinner"], "medium", "standard", "鱼头豆腐汤", 68, (650, 1100), "页面列举糟钵斗；具体食材与做法不得由文章外推。"),
    _row("fermented-bean-share", "豆豉风味蒸鱼合餐", "发酵风味合菜", "shared_dishes", "regional_share", "cn_cantonese", "rice", ["fish"], "shared", ["lunch", "dinner"], "medium", "standard", "清蒸鲈鱼", 78, (650, 1100), "页面列举豆豉及蒸鱼语境；组合菜名待菜单证据。"),
    _row("sichuan-pickle-share", "四川泡菜小菜拼盘", "传统发酵小菜", "shared_dishes", "regional_share", "cn_sichuan", "rice", ["none"], "shared", ["lunch", "dinner"], "high", "budget", "凉拌海带丝", 80, (300, 650), "页面列举四川泡菜；不将其宣传为健康功效。"),
    _row("millet-yellow-momo", "陕北糜子面黄馍馍拼盘", "地方主食拼盘", "shared_dishes", "regional_share", "cn_northwest", "wheat_bread", ["none"], "shared", ["breakfast", "snack"], "high", "budget", "杂粮馒头", 84, (500, 900), "页面列举陕北糜子面黄馍馍；拼盘份量待审核。"),
    _row("suzhou-bai-an", "苏州白案点心拼盘", "地方点心拼盘", "shared_dishes", "regional_share", "cn_jiangzhe", "wheat_bread", ["none"], "shared", ["breakfast", "snack"], "medium", "standard", "小笼包", 86, (500, 900), "页面列举苏州白案点心；不复制原文配方。"),
    _row("jiangnan-cake-share", "江南传统糕点拼盘", "江南糕点", "shared_dishes", "regional_share", "cn_jiangzhe", "wheat_bread", ["none"], "shared", ["snack"], "high", "budget", "发糕", 82, (500, 900), "页面列举条头糕、重阳糕、黄松糕等；组合待审核。"),
    _row("zongzi-share", "端午粽子分享餐", "节令点心", "shared_dishes", "regional_share", "cn_national", "mixed", ["pork"], "shared", ["breakfast", "snack"], "high", "budget", "糯米鸡", 82, (600, 1100), "页面列举粽子；节令可得性与份量待审核。"),
    _row("qing-tuan-share", "江南青团分享餐", "节令点心", "shared_dishes", "regional_share", "cn_jiangzhe", "wheat_bread", ["none"], "shared", ["snack"], "high", "budget", "红豆包子", 82, (500, 900), "页面列举青团；共享份型待审核。"),
    _row("honggui-share", "闽南红龟粿分享餐", "地方糕点", "shared_dishes", "regional_share", "cn_fujian", "wheat_bread", ["none"], "shared", ["snack"], "high", "budget", "红豆包子", 82, (500, 900), "页面列举红龟粿；共享份型待审核。"),
    _row("tanggua-tea", "山东糖瓜茶点", "节令糖点", "shared_dishes", "regional_share", "cn_shandong", "wheat_bread", ["none"], "shared", ["snack"], "high", "budget", "冰糖葫芦", 74, (450, 900), "页面列举糖瓜；糖分与适用人群待审核。"),
    _row("guangxi-chapao", "广西茶泡蜜饯拼盘", "地方蜜饯", "shared_dishes", "regional_share", "cn_national", "none", ["none"], "shared", ["snack"], "high", "standard", "陈皮红豆沙", 70, (450, 900), "页面列举茶泡；不推断营养功效。"),
    _row("northwest-paomo-share", "西北羊肉泡馍家庭餐", "地方汤食合餐", "shared_dishes", "regional_share", "cn_northwest", "wheat_bread", ["lamb"], "shared", ["lunch", "dinner"], "medium", "standard", "羊肉汤", 88, (900, 1400), "页面列举羊肉泡馍；家庭份量与汤汁配送需审核。"),
    _row("south-tangyuan-share", "南方元宵节令分享餐", "节令点心", "shared_dishes", "regional_share", "cn_national", "dumpling_wrapper", ["none"], "shared", ["breakfast", "snack"], "medium", "budget", "红豆包子", 78, (550, 1000), "页面列举南方元宵；节令和份量待审核。"),
    _row("xian-newyear-platter", "西安年节面食拼盘", "地方年节主食", "shared_dishes", "regional_share", "cn_northwest", "wheat_bread", ["pork"], "shared", ["lunch", "dinner"], "high", "standard", "西安腊汁肉夹馍", 82, (650, 1100), "页面列举腊汁肉夹馍；拼盘组合待审核。"),
    _row("yunnan-ham-rice", "云南火腿配杂粮饭", "地方风味套餐", "set_meal", "balanced_plate", "cn_yunnan_guizhou", "whole_grain", ["pork"], "shared", ["lunch", "dinner"], "high", "standard", "杂粮饭", 80, (650, 1050), "页面列举云南火腿；米饭配比和共享语义待审核。"),
    _row("benbang-home-share", "本帮菜家常合菜", "本帮合菜", "shared_dishes", "homestyle_share", "cn_jiangzhe", "rice", ["pork", "soy"], "shared", ["lunch", "dinner"], "medium", "standard", "红烧肉", 80, (750, 1250), "页面列举上海本帮菜；具体合菜组成待审核。"),
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
    SEED.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"candidate_batch1_ok added={added} total={len(rows)} status=draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
