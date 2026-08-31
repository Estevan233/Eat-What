"""Append a second conservative batch from a browser-verified ICH page.

The page lists these traditional-food project names and their regional context.
It does not establish menu portions, delivery fitness or nutrition, so every
row remains draft until those facts receive separate evidence and review.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "external_dining_seed.json"
SOURCE_URL = "https://www.ihchina.cn/project_details/23794.html"
CHECKED_AT = "2026-08-31T18:40:00+08:00"


def _row(
    key: str,
    name: str,
    category: str,
    family: str,
    sub_family: str,
    region: str,
    staple: str,
    proteins: list[str],
    anchor: str,
    score: int,
    energy: tuple[int, int],
    note: str,
) -> dict[str, object]:
    return {
        "catalog_key": f"external:batch2-{key}:v1",
        "legacy_key": None,
        "dish_name": name,
        "aliases": [],
        "category": category,
        "meal_family": family,
        "sub_family": sub_family,
        "cuisine_region": region,
        "staple_type": staple,
        "protein_types": proteins,
        "serving_style": "individual",
        "meal_periods": ["breakfast", "lunch", "dinner"],
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
            "来源核验：中国非遗网页面列出该传统面食/糕点项目及地域；"
            "仅作候选发现依据，未从该页推断菜单、份量、配送、营养或功效。"
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
    _row("zhongning-haozi-noodle", "中宁蒿子面", "地方传统面食", "noodle_meal", "noodle_soup", "cn_northwest", "wheat_noodle", ["none"], "阳春面", 82, (400, 700), "页面相关项目明确列出中宁蒿子面制作技艺。"),
    _row("jinyun-shaobing", "缙云烧饼", "地方烧饼", "wrap_light_meal", "wrap", "cn_jiangzhe", "wheat_bread", ["unknown"], "牛肉蔬菜卷饼", 72, (350, 650), "页面相关项目明确列出缙云烧饼制作技艺；馅料待审核。"),
    _row("shaoyongfeng-ma-bing", "邵永丰麻饼", "地方糕点", "snack_dessert", "snack", "cn_jiangzhe", "wheat_bread", ["unknown"], "发糕", 70, (280, 560), "页面相关项目明确列出邵永丰麻饼制作技艺。"),
    _row("li-liangui-smoked-pancake", "李连贵熏肉大饼", "东北面食", "wrap_light_meal", "wrap", "cn_northeast", "wheat_bread", ["unknown"], "牛肉蔬菜卷饼", 80, (450, 800), "页面相关项目明确列出该传统面食制作技艺；肉类与份型待审核。"),
    _row("taigu-bing", "太谷饼", "地方糕点", "snack_dessert", "snack", "cn_northwest", "wheat_bread", ["unknown"], "发糕", 80, (280, 560), "页面相关项目明确列出太谷饼制作技艺。"),
    _row("goubuli-baozi", "天津狗不理包子", "地方包点", "dumpling_bun", "steamed_bun", "cn_beijing_tianjin", "wheat_bread", ["unknown"], "小笼包", 78, (380, 680), "页面相关项目明确列出天津狗不理包子制作技艺；品牌相关字段不复制。"),
    _row("minjian-noodle", "抿尖面", "山西面食", "noodle_meal", "noodle_soup", "cn_northwest", "wheat_noodle", ["none"], "阳春面", 80, (380, 680), "页面相关项目明确列出抿尖面制作技艺。"),
    _row("maoerduo-noodle", "猫耳朵", "山西面食", "noodle_meal", "noodle_soup", "cn_northwest", "wheat_noodle", ["none"], "阳春面", 80, (380, 680), "页面相关项目明确列出猫耳朵制作技艺。"),
    _row("longxu-lamian", "龙须拉面", "山西面食", "noodle_meal", "noodle_soup", "cn_northwest", "wheat_noodle", ["none"], "阳春面", 82, (400, 720), "页面相关项目明确列出龙须拉面制作技艺。"),
    _row("daoxiao-noodle", "刀削面", "山西面食", "noodle_meal", "noodle_soup", "cn_northwest", "wheat_noodle", ["none"], "阳春面", 84, (420, 760), "页面相关项目明确列出刀削面制作技艺。"),
    _row("tatar-pastry", "塔塔尔族传统糕点", "民族糕点", "snack_dessert", "snack", "cn_northwest", "wheat_bread", ["unknown"], "发糕", 68, (300, 650), "页面相关项目明确列出塔塔尔族传统糕点制作技艺。"),
    _row("jishan-pastry", "稷山传统面点", "地方传统面点", "snack_dessert", "snack", "cn_northwest", "wheat_bread", ["unknown"], "发糕", 70, (300, 650), "页面相关项目明确列出稷山传统面点制作技艺。"),
    _row("xian-jiasan-tangbao", "西安贾三灌汤包子", "地方包点", "dumpling_bun", "dim_sum", "cn_northwest", "dumpling_wrapper", ["unknown"], "小笼包", 84, (380, 680), "页面相关项目明确列出西安贾三灌汤包子制作技艺；汤汁配送风险待审核。"),
    _row("laosun-yangrou-paomo", "老孙家羊肉泡馍", "地方汤食", "soup_meal", "stew_soup_set", "cn_northwest", "wheat_bread", ["lamb"], "羊肉汤", 86, (600, 950), "页面相关项目明确列出老孙家羊肉泡馍制作技艺；份量和商户菜单待审核。"),
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
    print(f"candidate_batch2_ok added={added} total={len(rows)} status=draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
