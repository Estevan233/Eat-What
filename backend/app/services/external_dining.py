"""Exposure-aware dining directions without merchant or LLM dependencies."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha1, sha256
from typing import Literal, cast
from uuid import uuid4

import structlog
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.core.config import get_settings
from app.core.errors import ValidationError
from app.models.dining_memory import DiningMemory
from app.models.recommendation_event import RecommendationEvent
from app.repositories.cloudbase_rdb import RdbFilter, RdbOrder
from app.repositories.cloudbase_repository import DatabaseSession, is_cloudbase_repository
from app.schemas.dining import (
    ExternalDiningRequest,
    ExternalDiningResponse,
    ExternalDiningSuggestion,
)
from app.services import dining_memory_service, profile_service
from app.services.solar_terms import get_today_context_cached

log = structlog.get_logger()
EXTERNAL_ENGINE = "external_rules_v2"
EXTERNAL_HISTORY_DAYS = 7
EXTERNAL_QUALITY_BAND = 5


@dataclass(frozen=True)
class RuleCandidate:
    dish_name: str
    category: str
    energy_min: int
    energy_max: int
    forbidden_tags: frozenset[str]
    nutrition_note: str
    warming: bool = False
    cooling: bool = False
    high_protein: bool = False
    meal_format: str = "individual_meal"
    serving_style: Literal["individual", "shared"] = "individual"
    catalog_key: str | None = None
    legacy_key: str | None = None


RULE_CANDIDATES: tuple[RuleCandidate, ...] = (
    RuleCandidate("番茄鸡蛋盖饭", "家常盖饭", 480, 650, frozenset(), "蛋类搭配番茄和主食，结构简单，注意酱汁少油。", meal_format="rice_bowl"),
    RuleCandidate("菌菇豆腐煲配米饭", "砂锅简餐", 450, 620, frozenset(), "豆制品和菌菇提供蛋白质与膳食纤维，搭配米饭组成一人份简餐。", warming=True, meal_format="claypot_set"),
    RuleCandidate("鸡肉时蔬饭", "均衡套餐", 520, 700, frozenset(), "鸡肉补充蛋白质，蔬菜和米饭组成相对完整的一餐。", high_protein=True, meal_format="balanced_plate"),
    RuleCandidate("南瓜小米粥配蒸蛋", "粥品套餐", 380, 560, frozenset(), "整体较清淡，蒸蛋补充蛋白质；粥类饱腹感因人而异。", warming=True, meal_format="congee_set"),
    RuleCandidate("清汤牛肉面", "汤面", 550, 750, frozenset({"beef", "gluten"}), "牛肉提供蛋白质，面食提供碳水；建议少汤少盐。", high_protein=True, warming=True, meal_format="noodle_soup"),
    RuleCandidate("清蒸鱼时蔬套餐", "蒸菜套餐", 480, 680, frozenset({"seafood"}), "鱼类和时蔬组合较清爽，确认鱼刺并少淋油汁。", high_protein=True, cooling=True, meal_format="steamed_set"),
    RuleCandidate("凉拌鸡丝荞麦面", "轻食拌面", 430, 620, frozenset({"gluten", "raw_cold"}), "鸡丝提供蛋白质，荞麦面和蔬菜增加饱腹感。", high_protein=True, cooling=True, meal_format="cold_noodle"),
    RuleCandidate("鱼香肉丝饭", "川味盖饭", 650, 850, frozenset({"pork", "spicy", "greasy"}), "能量通常偏高，建议少油少糖并加一份蔬菜。", meal_format="spicy_rice_bowl"),
    RuleCandidate("鲜虾蔬菜馄饨", "汤馄饨", 430, 620, frozenset({"seafood", "gluten"}), "馄饨提供主食和蛋白质，另加青菜比只喝汤更完整。", high_protein=True, warming=True, meal_format="wonton_soup"),
    RuleCandidate("香菇鸡肉焖饭", "焖饭", 500, 700, frozenset(), "鸡肉、香菇和米饭一碗组合，建议额外搭配一份深色蔬菜。", high_protein=True, warming=True, meal_format="braised_rice"),
    RuleCandidate("鸡蛋蔬菜卷配玉米", "轻简套餐", 420, 600, frozenset({"gluten"}), "蛋类和蔬菜卷搭配玉米，适合作为分量清楚的一人餐。", high_protein=True, meal_format="wrap_set"),
    RuleCandidate("番茄牛腩粉", "汤粉", 520, 740, frozenset({"beef"}), "牛腩补充蛋白质，番茄汤底注意盐分，粉量按活动量调整。", high_protein=True, warming=True, meal_format="rice_noodle_soup"),
    RuleCandidate("鸡腿肉蔬菜糙米饭", "谷物套餐", 520, 720, frozenset(), "鸡腿肉、蔬菜和糙米构成完整一餐，酱汁分装更容易控制油盐。", high_protein=True, meal_format="grain_bowl"),
    RuleCandidate("海南鸡饭配青菜", "东南亚简餐", 560, 760, frozenset(), "鸡肉提供蛋白质，米饭和蘸料能量不低，建议加青菜并按需减饭。", high_protein=True, meal_format="hainanese_set"),
    RuleCandidate("虾仁滑蛋饭配时蔬", "滑蛋饭", 520, 720, frozenset({"seafood"}), "虾仁和鸡蛋提供蛋白质，搭配时蔬后结构更完整。", high_protein=True, meal_format="egg_rice_set"),
    RuleCandidate("烤鲭鱼定食", "烤鱼定食", 520, 740, frozenset({"seafood"}), "鱼类、米饭和小菜组成定食，注意酱汁与腌菜的钠含量。", high_protein=True, meal_format="grilled_fish_set"),
    RuleCandidate("香煎豆腐杂蔬饭", "豆腐简餐", 440, 640, frozenset(), "豆腐搭配多种蔬菜和主食，煎制用油量决定实际能量。", meal_format="tofu_bowl"),
    RuleCandidate("番茄鸡蛋面配青菜", "家常汤面", 480, 680, frozenset({"gluten"}), "番茄鸡蛋面容易执行，额外加青菜并少喝汤更均衡。", warming=True, meal_format="homestyle_noodle"),
    RuleCandidate("三鲜米线配青菜", "米线", 480, 700, frozenset({"seafood"}), "米线提供主食，三鲜配料与青菜补充蛋白质和蔬菜，汤底宜少盐。", warming=True, meal_format="rice_noodle_set"),
    RuleCandidate("鸡肉蔬菜河粉", "清汤河粉", 500, 700, frozenset(), "鸡肉、河粉和蔬菜组成清汤简餐，可要求少汤少盐。", high_protein=True, meal_format="pho_set"),
    RuleCandidate("牛肉蔬菜卷饼", "卷饼套餐", 500, 720, frozenset({"beef", "gluten"}), "牛肉和蔬菜卷入饼中，酱料分装并搭配无糖饮品更稳妥。", high_protein=True, meal_format="beef_wrap"),
    RuleCandidate("鹰嘴豆蔬菜卷配玉米", "素食卷饼", 430, 620, frozenset({"gluten"}), "鹰嘴豆提供植物蛋白，蔬菜卷与玉米组合成分量清楚的一餐。", meal_format="legume_wrap"),
    RuleCandidate("莲藕排骨汤配时蔬饭", "汤菜套餐", 560, 780, frozenset({"pork"}), "排骨、莲藕、时蔬和米饭组成套餐，汤不必全部喝完。", high_protein=True, warming=True, meal_format="pork_soup_set"),
    RuleCandidate("冬瓜虾仁汤配杂粮饭", "清汤套餐", 460, 660, frozenset({"seafood"}), "虾仁补充蛋白质，冬瓜汤和杂粮饭组成较清爽的一餐。", high_protein=True, cooling=True, meal_format="light_soup_set"),
    RuleCandidate("麻婆豆腐饭配青菜", "川味豆腐饭", 560, 780, frozenset({"spicy"}), "豆腐搭配米饭和青菜，实际油盐差异较大，可备注少油少辣。", meal_format="spicy_tofu_rice"),
    RuleCandidate("咖喱鸡肉饭配蔬菜", "咖喱饭", 600, 820, frozenset(), "鸡肉提供蛋白质，咖喱酱和米饭较易超量，建议酱汁减半并加蔬菜。", high_protein=True, warming=True, meal_format="curry_rice"),
    RuleCandidate("黑椒牛柳饭配彩椒", "铁板牛肉饭", 620, 840, frozenset({"beef"}), "牛柳和彩椒提供蛋白质与蔬菜，黑椒汁宜分装以控制油盐。", high_protein=True, meal_format="beef_rice_set"),
    RuleCandidate("红烧豆腐杂粮饭", "家常素套餐", 460, 660, frozenset(), "豆腐、蔬菜和杂粮饭组成家常套餐，红烧汁少一些更合适。", meal_format="vegetarian_set"),
    RuleCandidate("云吞面配白灼菜", "粤式面食", 520, 720, frozenset({"pork", "gluten"}), "云吞和面提供主食与蛋白质，另配白灼菜并少喝汤。", warming=True, meal_format="wonton_noodle"),
    RuleCandidate("鸡肉蔬菜沙拉配玉米", "轻食套餐", 400, 620, frozenset({"raw_cold"}), "鸡肉、蔬菜和玉米组成轻食，沙拉酱另放，避免只吃菜不吃主食。", high_protein=True, cooling=True, meal_format="salad_set"),
    RuleCandidate("烤鸡腿土豆时蔬套餐", "烤物套餐", 560, 780, frozenset(), "烤鸡腿、土豆和时蔬结构完整，选择非油炸并减少重口酱料。", high_protein=True, meal_format="roast_set"),
    RuleCandidate("韩式杂蔬拌饭", "拌饭", 520, 740, frozenset({"spicy"}), "多种蔬菜、鸡蛋和米饭组合，辣酱分装可减少盐和糖。", meal_format="bibimbap"),
    RuleCandidate("腊味煲仔饭配青菜", "煲仔饭", 680, 900, frozenset({"pork", "greasy"}), "腊味和锅巴使能量、钠含量偏高，适合偶尔选择并加一份青菜。", warming=True, meal_format="claypot_rice"),
    RuleCandidate("酸汤鱼片粉", "酸汤粉", 540, 760, frozenset({"seafood", "spicy"}), "鱼片补充蛋白质，酸汤和配料钠含量可能较高，少喝汤更稳妥。", high_protein=True, meal_format="sour_fish_noodle"),
    RuleCandidate("肉末茄子饭配青菜", "家常盖浇饭", 600, 820, frozenset({"pork", "greasy"}), "茄子吸油，建议备注少油并搭配一份清淡青菜。", meal_format="minced_pork_rice"),
    RuleCandidate("香菇鸡肉蒸饭", "蒸饭", 500, 700, frozenset(), "鸡肉、香菇和米饭同蒸，搭配一份蔬菜即可形成完整简餐。", high_protein=True, warming=True, meal_format="steamed_rice"),
    RuleCandidate(
        "番茄炒蛋＋菌菇豆腐＋时蔬＋杂粮饭",
        "家常合菜",
        480,
        680,
        frozenset(),
        "共享菜兼顾蛋类、豆制品、蔬菜和主食，按人数控制总量。",
        meal_format="shared_dishes",
        serving_style="shared",
    ),
    RuleCandidate(
        "菌汤火锅＋豆腐蔬菜拼盘＋主食",
        "清汤火锅",
        520,
        760,
        frozenset(),
        "清汤锅底便于多人共享，优先蔬菜和豆制品，蘸料少油少盐。",
        warming=True,
        meal_format="hotpot",
        serving_style="shared",
    ),
    RuleCandidate(
        "蒸点拼盘＋粥＋青菜",
        "广式茶点",
        480,
        720,
        frozenset({"gluten"}),
        "小份蒸点适合多人分食，搭配粥和青菜，避免只点精制点心。",
        meal_format="dim_sum",
        serving_style="shared",
    ),
    RuleCandidate(
        "清蒸鱼＋时蔬＋杂粮饭",
        "清蒸合菜",
        500,
        720,
        frozenset({"seafood"}),
        "鱼类、时蔬和主食组成共享套餐，注意鱼刺并少淋油汁。",
        high_protein=True,
        cooling=True,
        meal_format="steamed_set",
        serving_style="shared",
    ),
    RuleCandidate(
        "砂锅鸡煲＋双份青菜＋米饭",
        "砂锅合餐",
        580,
        820,
        frozenset(),
        "鸡肉煲适合共享，另点两份不同青菜，酱汁和米饭按需添加。",
        high_protein=True,
        warming=True,
        meal_format="claypot",
        serving_style="shared",
    ),
    RuleCandidate(
        "番茄牛腩锅＋凉热双蔬＋主食",
        "炖锅合餐",
        600,
        850,
        frozenset({"beef"}),
        "炖锅便于多人分享，搭配两种蔬菜和适量主食，避免汤汁泡饭过量。",
        high_protein=True,
        warming=True,
        meal_format="stew_pot",
        serving_style="shared",
    ),
    RuleCandidate(
        "铁板鸡肉＋彩椒洋葱＋米饭",
        "铁板合餐",
        560,
        800,
        frozenset(),
        "铁板鸡肉适合多人分食，搭配彩色蔬菜，酱汁另放可减少油盐。",
        high_protein=True,
        meal_format="sizzling_plate",
        serving_style="shared",
    ),
    RuleCandidate(
        "云南菌菇汽锅＋豆腐＋时蔬＋杂粮饭",
        "云南汽锅",
        460,
        680,
        frozenset(),
        "菌菇、豆腐和时蔬组成清淡共享餐，汤只作搭配，不靠喝汤补营养。",
        warming=True,
        meal_format="steam_pot",
        serving_style="shared",
    ),
    RuleCandidate(
        "什锦素烩菜＋蒸蛋＋杂粮饭",
        "北方烩菜",
        500,
        720,
        frozenset(),
        "烩菜和蒸蛋便于多人分食，食材种类较多，主食按家庭习惯选择。",
        warming=True,
        meal_format="homestyle_stew",
        serving_style="shared",
    ),
    RuleCandidate(
        "白切鸡＋白灼时蔬＋例汤＋米饭",
        "粤式合菜",
        520,
        760,
        frozenset(),
        "白切鸡和白灼菜适合共享，蘸料分装、米饭按人数添加。",
        high_protein=True,
        meal_format="cantonese_set",
        serving_style="shared",
    ),
    RuleCandidate(
        "客家酿豆腐＋时蔬小炒＋杂粮饭",
        "客家合菜",
        520,
        760,
        frozenset({"pork"}),
        "酿豆腐兼有豆制品和肉类，搭配时蔬与主食组成共享餐。",
        high_protein=True,
        meal_format="hakka_set",
        serving_style="shared",
    ),
    RuleCandidate(
        "小鸡炖蘑菇＋凉拌菜＋杂粮饭",
        "东北炖菜",
        560,
        800,
        frozenset(),
        "炖鸡和蘑菇适合多人共享，另配清爽蔬菜，主食按需选择。",
        high_protein=True,
        warming=True,
        meal_format="northeast_stew",
        serving_style="shared",
    ),
    RuleCandidate(
        "清炖狮子头＋双份时蔬＋米饭",
        "江浙合菜",
        620,
        850,
        frozenset({"pork"}),
        "狮子头分食并搭配两种蔬菜，减少浓汁拌饭可控制能量。",
        meal_format="jiangnan_set",
        serving_style="shared",
    ),
    RuleCandidate(
        "湘味小炒肉＋蒸蛋＋时蔬＋米饭",
        "湘菜合餐",
        650,
        880,
        frozenset({"pork", "spicy", "greasy"}),
        "小炒肉口味较重，以蒸蛋和时蔬平衡，备注少油少辣。",
        meal_format="hunan_set",
        serving_style="shared",
    ),
    RuleCandidate(
        "烧味双拼＋白灼菜＋例汤＋米饭",
        "烧味合餐",
        650,
        900,
        frozenset({"pork", "greasy"}),
        "烧味便于多人分食但钠和脂肪偏高，搭配白灼菜且少淋汁。",
        meal_format="roast_meat_set",
        serving_style="shared",
    ),
    RuleCandidate(
        "清汤牛肉锅＋菌菇蔬菜拼盘＋主食",
        "牛肉锅",
        580,
        820,
        frozenset({"beef"}),
        "清汤牛肉锅适合共享，蔬菜和菌菇先点足，蘸料少油少盐。",
        high_protein=True,
        warming=True,
        meal_format="beef_hotpot",
        serving_style="shared",
    ),
    RuleCandidate(
        "酸菜鱼小份＋时蔬＋豆腐＋米饭",
        "酸菜鱼合餐",
        620,
        860,
        frozenset({"seafood", "spicy"}),
        "鱼片、豆腐和蔬菜可共享，酸菜汤钠含量高，不建议大量喝汤。",
        high_protein=True,
        meal_format="pickled_fish_set",
        serving_style="shared",
    ),
    RuleCandidate(
        "烤鱼小份＋双拼蔬菜＋主食",
        "烤鱼合餐",
        650,
        900,
        frozenset({"seafood", "spicy", "greasy"}),
        "烤鱼适合多人分享，选择小份并加两种蔬菜，避免额外油炸小吃。",
        high_protein=True,
        meal_format="grilled_fish_share",
        serving_style="shared",
    ),
    RuleCandidate(
        "家常豆腐＋地三鲜少油版＋蒸蛋＋杂粮饭",
        "素菜合餐",
        520,
        760,
        frozenset(),
        "豆腐、鸡蛋和多种蔬菜适合共享，地三鲜可备注少油。",
        meal_format="vegetarian_share",
        serving_style="shared",
    ),
    RuleCandidate(
        "大盘鸡小份＋拌青菜＋面或米饭",
        "西北合餐",
        650,
        900,
        frozenset({"gluten", "spicy"}),
        "鸡肉和土豆适合共享，主食二选一并加一份清淡蔬菜。",
        high_protein=True,
        warming=True,
        meal_format="northwest_share",
        serving_style="shared",
    ),
    RuleCandidate(
        "铁板豆腐＋清炒虾仁＋双份时蔬＋米饭",
        "海陆合菜",
        560,
        800,
        frozenset({"seafood"}),
        "豆腐、虾仁和两种蔬菜覆盖多类食材，酱汁分装更易控制油盐。",
        high_protein=True,
        meal_format="seafood_share",
        serving_style="shared",
    ),
)


def _seasonal_note(month: int, solar_term: str) -> str:
    suffix = f"（临近{solar_term}）" if solar_term else ""
    if month in {12, 1, 2}:
        return f"冬季可优先温热、熟食和适量汤羹{suffix}，仅作日常饮食参考。"
    if month in {6, 7, 8}:
        return f"夏季可优先清淡、少油并注意补水{suffix}，不把寒凉当成万能答案。"
    if month in {3, 4, 5}:
        return f"春季搭配新鲜蔬菜和优质蛋白{suffix}，比追逐单一“养生食材”更稳妥。"
    return f"秋季注意蔬菜、蛋白质与主食均衡{suffix}，节气只作轻量参考。"


def _memory_suggestion(
    memory: DiningMemory,
    request: ExternalDiningRequest,
    seasonal_note: str,
    city_label: str,
) -> ExternalDiningSuggestion:
    keywords = [part for part in (city_label, memory.shop_name, memory.dish_name) if part != "未设置城市"]
    tips = ["下单前确认门店与菜名，备注只作为你的私人参考", "优先选择少油少盐、酱汁分装"]
    if request.audience == "family":
        tips.insert(0, f"按 {request.party_size} 人份核对分量，主食和蔬菜可分开加购")
    return ExternalDiningSuggestion(
        key=f"memory-{memory.id}",
        shop_name=memory.shop_name,
        dish_name=memory.dish_name,
        category="吃过的店",
        meal_format="saved_choice",
        serving_style="individual",
        energy_kcal_min_per_person=450,
        energy_kcal_max_per_person=750,
        search_keywords=keywords,
        order_tips=tips,
        reason="你曾标记喜欢；仍建议结合当天口味和实际菜单判断。",
        seasonal_note=seasonal_note,
        nutrition_note="门店配方和分量未知，能量仅给宽区间，不冒充精确营养计算。",
        source="memory",
    )


def _rule_score(candidate: RuleCandidate, request: ExternalDiningRequest, month: int) -> int:
    score = 50
    if request.activity_level == "high" and candidate.high_protein:
        score += 8
    if request.mood == "tired" and candidate.high_protein:
        score += 4
    if month in {12, 1, 2} and candidate.warming:
        score += 3
    if month in {6, 7, 8} and candidate.cooling:
        score += 3
    return score


def _rule_suggestion(
    candidate: RuleCandidate,
    request: ExternalDiningRequest,
    seasonal_note: str,
    city_label: str,
) -> ExternalDiningSuggestion:
    digest = sha1(f"{candidate.category}:{candidate.dish_name}".encode()).hexdigest()[:10]
    keywords = [part for part in (city_label, candidate.dish_name, candidate.category) if part != "未设置城市"]
    tips = ["优先查看近期评价和实际分量", "备注少油少盐、酱汁分装，饮料默认无糖"]
    if request.audience == "family":
        tips.insert(0, f"按 {request.party_size} 人份下单，先确定共享菜再补主食")
    return ExternalDiningSuggestion(
        key=candidate.legacy_key or candidate.catalog_key or f"rule-{digest}",
        dish_name=candidate.dish_name,
        category=candidate.category,
        meal_format=candidate.meal_format,
        serving_style=candidate.serving_style,
        energy_kcal_min_per_person=candidate.energy_min,
        energy_kcal_max_per_person=candidate.energy_max,
        search_keywords=keywords,
        order_tips=tips,
        reason=candidate.nutrition_note or "兼顾营养结构与近期不重复。",
        seasonal_note=seasonal_note,
        nutrition_note=candidate.nutrition_note,
        source="rules",
    )


def _load_request_event(
    session: DatabaseSession,
    request_id: str,
) -> RecommendationEvent | None:
    if is_cloudbase_repository(session):
        return session.first(
            RecommendationEvent,
            filters=(RdbFilter("request_id", "eq", request_id),),
        )
    return session.exec(
        select(RecommendationEvent).where(
            RecommendationEvent.request_id == request_id,
        )
    ).first()


def _suggestion_keys_from_event(
    event: RecommendationEvent,
    *,
    user_id: int,
) -> list[str] | None:
    if event.user_id != user_id:
        raise ValidationError("推荐请求号已被占用")
    payload = event.primary_meal_json or {}
    if payload.get("kind") != "external_dining_v2":
        return None
    raw_keys = payload.get("suggestion_keys")
    if not isinstance(raw_keys, list):
        return None
    keys = [value for value in raw_keys if isinstance(value, str)]
    if len(keys) != len(raw_keys):
        return None
    return keys


def _load_recent_external_events(
    session: DatabaseSession,
    user_id: int,
    *,
    as_of: date,
) -> list[RecommendationEvent]:
    start = as_of - timedelta(days=EXTERNAL_HISTORY_DAYS - 1)
    if is_cloudbase_repository(session):
        return session.list(
            RecommendationEvent,
            filters=(
                RdbFilter("user_id", "eq", user_id),
                RdbFilter("event_date", "gte", start),
                RdbFilter("event_date", "lte", as_of),
                RdbFilter("dining_mode", "eq", "eat_out"),
            ),
            order=(RdbOrder("created_at", "desc"),),
        )
    stmt = (
        select(RecommendationEvent)
        .where(RecommendationEvent.user_id == user_id)
        .where(RecommendationEvent.event_date >= start)
        .where(RecommendationEvent.event_date <= as_of)
        .where(RecommendationEvent.dining_mode == "eat_out")
        .order_by(RecommendationEvent.created_at.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


def _recent_external_keys(events: Sequence[RecommendationEvent]) -> set[str]:
    keys: set[str] = set()
    for event in events:
        summary = event.summary_json or {}
        raw_keys = summary.get("suggestion_keys", [])
        if not isinstance(raw_keys, list):
            continue
        keys.update(value for value in raw_keys if isinstance(value, str))
    return keys


def _exploration_key(
    suggestion: ExternalDiningSuggestion,
    *,
    base_score: int,
    floor_score: int,
    user_id: int,
    event_date: date,
    request_id: str,
) -> float:
    payload = (
        f"{user_id}|{event_date.isoformat()}|{request_id}|"
        f"{EXTERNAL_ENGINE}|{suggestion.key}"
    )
    digest = sha256(payload.encode()).digest()
    uniform = (int.from_bytes(digest[:8], "big") + 1) / (2**64 + 1)
    quality_weight = 1.0 + max(0, base_score - floor_score)
    return -math.log(uniform) / quality_weight


def _stable_exploration_order(
    scored: Sequence[tuple[ExternalDiningSuggestion, int]],
    *,
    user_id: int,
    event_date: date,
    request_id: str,
) -> list[ExternalDiningSuggestion]:
    """只在质量带内探索；同用户同 request_id 可复现，不同用户不锁死。"""
    if not scored:
        return []
    highest = max(score for _, score in scored)
    floor_score = highest - EXTERNAL_QUALITY_BAND
    in_band = [(item, score) for item, score in scored if score >= floor_score]
    outside = [(item, score) for item, score in scored if score < floor_score]
    in_band.sort(
        key=lambda pair: _exploration_key(
            pair[0],
            base_score=pair[1],
            floor_score=floor_score,
            user_id=user_id,
            event_date=event_date,
            request_id=request_id,
        )
    )
    outside.sort(
        key=lambda pair: (
            -pair[1],
            _exploration_key(
                pair[0],
                base_score=pair[1],
                floor_score=pair[1],
                user_id=user_id,
                event_date=event_date,
                request_id=request_id,
            ),
        )
    )
    return [item for item, _ in (*in_band, *outside)]


def _record_external_response(
    session: DatabaseSession,
    user_id: int,
    request: ExternalDiningRequest,
    response: ExternalDiningResponse,
    *,
    request_id: str,
    event_date: date,
) -> None:
    suggestions = response.suggestions
    event = RecommendationEvent(
        request_id=request_id,
        user_id=user_id,
        event_date=event_date,
        recommended_food_ids_json=[],
        primary_food_ids_json=[],
        substitution_options_json=[],
        primary_meal_json={
            "kind": "external_dining_v2",
            # 只保存匿名方向 key，不保存城市、坐标或搜索关键词。
            "suggestion_keys": [item.key for item in suggestions],
        },
        mood=request.mood,
        activity_level=request.activity_level,
        weather_tag=None,
        dining_mode="eat_out",
        audience=request.audience,
        party_size=request.party_size,
        engine=EXTERNAL_ENGINE,
        scorer_version=EXTERNAL_ENGINE,
        builder_version="external_builder_v2",
        summary_json={
            "suggestion_keys": [item.key for item in suggestions],
            "meal_formats": [item.meal_format for item in suggestions],
        },
    )
    try:
        if is_cloudbase_repository(session):
            session.insert(event)
            return
        session.add(event)
        session.commit()
    except IntegrityError:
        if not is_cloudbase_repository(session):
            session.rollback()
        # 并发重试可能已写入同一 request_id；调用方下一次会直接重放。
        return
    except Exception as exc:  # 推荐可用性优先，曝光写入失败不阻断本次结果
        if not is_cloudbase_repository(session):
            session.rollback()
        log.warning(
            "external_recommendation_event_write_failed",
            user_id=user_id,
            request_id=request_id,
            error_type=type(exc).__name__,
        )


def select_rotating_suggestions(
    ordered: Sequence[ExternalDiningSuggestion],
    excluded_keys: set[str],
    *,
    size: int = 3,
) -> tuple[list[ExternalDiningSuggestion], bool]:
    """Prefer unseen meal formats, then unseen items, then bounded reuse."""
    selected: list[ExternalDiningSuggestion] = []
    selected_keys: set[str] = set()
    selected_formats: set[str] = set()

    for require_new_format in (True, False):
        for suggestion in ordered:
            if len(selected) >= size:
                return selected, False
            if suggestion.key in excluded_keys or suggestion.key in selected_keys:
                continue
            if require_new_format and suggestion.meal_format in selected_formats:
                continue
            selected.append(suggestion)
            selected_keys.add(suggestion.key)
            selected_formats.add(suggestion.meal_format)

    rotation_restarted = len(selected) < size
    for suggestion in ordered:
        if len(selected) >= size:
            break
        if suggestion.key in selected_keys:
            continue
        selected.append(suggestion)
        selected_keys.add(suggestion.key)
    return selected, rotation_restarted


def _select_response_suggestions(
    session: DatabaseSession,
    user_id: int,
    request: ExternalDiningRequest,
    ordered_suggestions: Sequence[ExternalDiningSuggestion],
    replay_keys: Sequence[str] | None,
    *,
    event_date: date,
) -> tuple[list[ExternalDiningSuggestion], bool]:
    """Replay an idempotent request or select a fresh exposure-aware batch."""
    if replay_keys is not None:
        by_key = {item.key: item for item in ordered_suggestions}
        suggestions = [by_key[key] for key in replay_keys if key in by_key]
        if len(suggestions) != len(replay_keys):
            raise ValidationError("原推荐方向已失效，请使用新的请求号重试")
        return suggestions, False

    recent_events = _load_recent_external_events(
        session,
        user_id,
        as_of=event_date,
    )
    excluded_keys = _recent_external_keys(recent_events)
    excluded_keys.update(request.exclude_keys)
    return select_rotating_suggestions(ordered_suggestions, excluded_keys)


def _load_catalog_rule_candidates(
    session: DatabaseSession,
) -> tuple[RuleCandidate, ...] | None:
    """Read approved catalog rows and adapt them to the legacy response contract."""
    from app.models.external_dining_candidate import ExternalDiningCandidate

    try:
        if is_cloudbase_repository(session):
            rows = session.list(
                ExternalDiningCandidate,
                filters=(
                    RdbFilter("review_status", "eq", "approved"),
                    RdbFilter("is_active", "is", True),
                ),
                order=(RdbOrder("id", "asc"),),
                limit=1000,
            )
        else:
            rows = list(session.exec(select(ExternalDiningCandidate)).all())
    except Exception as exc:
        log.warning(
            "external_catalog_read_failed",
            error_type=type(exc).__name__,
        )
        return None

    adapted: list[RuleCandidate] = []
    for row in rows:
        if row.energy_kcal_min_per_person is None or row.energy_kcal_max_per_person is None:
            continue
        adapted.append(
            RuleCandidate(
                dish_name=row.dish_name,
                category=row.category,
                energy_min=row.energy_kcal_min_per_person,
                energy_max=row.energy_kcal_max_per_person,
                forbidden_tags=frozenset(row.forbidden_tags_json or []),
                nutrition_note=row.nutrition_note or "门店配方和分量未知，能量仅作宽区间参考。",
                high_protein=row.high_protein,
                meal_format=row.sub_family,
                serving_style=(
                    "individual"
                    if row.serving_style == "either"
                    else cast(Literal["individual", "shared"], row.serving_style)
                ),
                catalog_key=row.catalog_key,
                legacy_key=row.legacy_key,
            )
        )
    return tuple(adapted) or None


def _rule_candidates_for_request(session: DatabaseSession) -> tuple[RuleCandidate, ...]:
    """Use the catalog only after an explicit flag and approved rows exist."""
    if not get_settings().external_catalog_enabled:
        return RULE_CANDIDATES
    return _load_catalog_rule_candidates(session) or RULE_CANDIDATES


def recommend_external(
    session: DatabaseSession,
    user_id: int,
    request: ExternalDiningRequest,
) -> ExternalDiningResponse:
    effective_request_id = request.request_id or str(uuid4())
    replay_keys: list[str] | None = None
    if request.request_id is not None:
        existing = _load_request_event(session, effective_request_id)
        if existing is not None:
            replay_keys = _suggestion_keys_from_event(existing, user_id=user_id)
            if replay_keys is None:
                raise ValidationError("推荐请求号已用于其他类型的推荐")

    profile = profile_service.get_profile(session, user_id)
    forbidden = set(profile.forbidden_tags if profile else [])
    memories = dining_memory_service.all_memories(session, user_id)
    liked = [item for item in memories if item.verdict == "liked"]

    today = get_today_context_cached()
    event_date = today.date
    month = today.date.month
    solar_term = today.solar_term_current or today.solar_term_next_name
    seasonal_note = _seasonal_note(month, solar_term)
    if request.city:
        city_label = request.city
    elif request.lat is not None and request.lng is not None:
        city_label = "当前位置附近"
    else:
        city_label = "未设置城市"

    scored_suggestions: list[tuple[ExternalDiningSuggestion, int]] = []
    if request.audience == "personal":
        scored_suggestions.extend(
            (
                _memory_suggestion(memory, request, seasonal_note, city_label),
                54,
            )
            for memory in liked
        )

    serving_style = "shared" if request.audience == "family" else "individual"
    rule_candidates = _rule_candidates_for_request(session)
    scored_suggestions.extend(
        (
            _rule_suggestion(candidate, request, seasonal_note, city_label),
            _rule_score(candidate, request, month),
        )
        for candidate in rule_candidates
        if candidate.serving_style == serving_style
        and not (candidate.forbidden_tags & forbidden)
    )
    ordered_suggestions = _stable_exploration_order(
        scored_suggestions,
        user_id=user_id,
        event_date=event_date,
        request_id=effective_request_id,
    )
    # 用户明确标记“喜欢”的真实店＋菜在未曝光时优先一次；之后仍受七日历史约束，
    # 避免“个性化”退化为每天重复同一家。
    memory_suggestions = [
        suggestion
        for suggestion, _ in scored_suggestions
        if suggestion.source == "memory"
    ]
    if memory_suggestions:
        memory_keys = {item.key for item in memory_suggestions}
        ordered_suggestions = [
            *memory_suggestions,
            *(item for item in ordered_suggestions if item.key not in memory_keys),
        ]

    suggestions, rotation_restarted = _select_response_suggestions(
        session,
        user_id,
        request,
        ordered_suggestions,
        replay_keys,
        event_date=event_date,
    )

    response = ExternalDiningResponse(
        audience=request.audience,
        party_size=request.party_size,
        city_label=city_label,
        suggestions=suggestions,
        rotation_restarted=rotation_restarted,
        disclaimer="门店、价格和营养会随实际情况变化；本结果是决策辅助，不是医疗或下单承诺。",
    )
    if replay_keys is None:
        _record_external_response(
            session,
            user_id,
            request,
            response,
            request_id=effective_request_id,
            event_date=event_date,
        )
    return response
