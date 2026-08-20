"""Deterministic rotating dining suggestions without merchant or LLM dependencies."""

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha1
from typing import Literal

from sqlmodel import Session

from app.models.dining_memory import DiningMemory
from app.schemas.dining import (
    ExternalDiningRequest,
    ExternalDiningResponse,
    ExternalDiningSuggestion,
)
from app.services import dining_memory_service, profile_service
from app.services.solar_terms import get_today_context_cached


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
        key=f"rule-{digest}",
        dish_name=candidate.dish_name,
        category=candidate.category,
        meal_format=candidate.meal_format,
        serving_style=candidate.serving_style,
        energy_kcal_min_per_person=candidate.energy_min,
        energy_kcal_max_per_person=candidate.energy_max,
        search_keywords=keywords,
        order_tips=tips,
        reason="兼顾营养结构、可执行性和近期不重复；天气只做很小修正。",
        seasonal_note=seasonal_note,
        nutrition_note=candidate.nutrition_note,
        source="rules",
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


def recommend_external(
    session: Session,
    user_id: int,
    request: ExternalDiningRequest,
) -> ExternalDiningResponse:
    profile = profile_service.get_profile(session, user_id)
    forbidden = set(profile.forbidden_tags if profile else [])
    memories = dining_memory_service.all_memories(session, user_id)
    liked = next((item for item in memories if item.verdict == "liked"), None)

    today = get_today_context_cached()
    month = today.date.month
    solar_term = today.solar_term_current or today.solar_term_next_name
    seasonal_note = _seasonal_note(month, solar_term)
    if request.city:
        city_label = request.city
    elif request.lat is not None and request.lng is not None:
        city_label = "当前位置附近"
    else:
        city_label = "未设置城市"

    ordered_suggestions: list[ExternalDiningSuggestion] = []
    if liked is not None and request.audience == "personal":
        ordered_suggestions.append(
            _memory_suggestion(liked, request, seasonal_note, city_label)
        )

    serving_style = "shared" if request.audience == "family" else "individual"
    ordered = sorted(
        (
            candidate
            for candidate in RULE_CANDIDATES
            if candidate.serving_style == serving_style
            and not (candidate.forbidden_tags & forbidden)
        ),
        key=lambda item: (-_rule_score(item, request, month), item.meal_format, item.dish_name),
    )
    used_formats: set[str] = set()
    for candidate in ordered:
        if candidate.meal_format in used_formats:
            continue
        ordered_suggestions.append(
            _rule_suggestion(candidate, request, seasonal_note, city_label)
        )
        used_formats.add(candidate.meal_format)

    suggestions, rotation_restarted = select_rotating_suggestions(
        ordered_suggestions,
        set(request.exclude_keys),
    )

    return ExternalDiningResponse(
        audience=request.audience,
        party_size=request.party_size,
        city_label=city_label,
        suggestions=suggestions,
        rotation_restarted=rotation_restarted,
        disclaimer="门店、价格和营养会随实际情况变化；本结果是决策辅助，不是医疗或下单承诺。",
    )
