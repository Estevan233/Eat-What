"""推荐算法核心 - 硬筛、规则评分、新鲜度、多样性与有界重排。

学习点：
- 纯函数式：所有外部依赖（profile/weather/today/history/foods）从函数参数注入，便于测试
- 主入口 recommend() 协调硬筛、评分、有界重排、七天降权、多样性和持久化
- 相同状态下排序确定；同日再次请求会根据新增曝光记录主动轮换
- 可选 Agent 只能调整已通过硬筛的候选，异常时回退规则排序
"""
from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from sqlmodel import Session, select

from app.core.errors import NotFoundError, ValidationError
from app.models.daily_log import DailyLog
from app.models.food import Food
from app.models.recipe import Recipe
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.daily import (
    ActivityLevel,
    FoodWithReason,
    Mood,
    RecommendContext,
    RecommendRequest,
    RecommendResponse,
)
from app.schemas.meal import MealBuildResult
from app.schemas.today_context import TodayContext
from app.schemas.weather import WeatherData, WeatherTag
from app.services import daily_service, food_service, profile_service
from app.services.meal_builder import MealCandidate, build_meal
from app.services.recommendation_ranking import (
    RULE_V3_WEIGHTS,
    CandidateReranker,
    IdentityReranker,
    RankedCandidate,
    RecommendationHistory,
    RecommendationRankingContext,
    ScoreBreakdown,
    apply_novelty,
    apply_rerank_adjustments,
    build_recommendation_history,
)
from app.services.solar_terms import get_today_context_cached
from app.services.weather_client import weather_client

log = structlog.get_logger()

# ---- 常量 ----

# 24 节气拼音 → 中文映射（lunar_python.getJieQi 返中文，food_seed 存拼音）
SOLAR_TERM_PINYIN_TO_ZH: dict[str, str] = {
    "lichun": "立春", "yushui": "雨水", "jingzhe": "惊蛰", "chunfen": "春分",
    "qingming": "清明", "guyu": "谷雨", "lixia": "立夏", "xiaoman": "小满",
    "mangzhong": "芒种", "xiazhi": "夏至", "xiaoshu": "小暑", "dachu": "大暑",
    "liqiu": "立秋", "chushu": "处暑", "bailu": "白露", "qiufen": "秋分",
    "hanlu": "寒露", "shuangjiang": "霜降", "lidong": "立冬", "xiaoxue": "小雪",
    "daxue": "大雪", "dongzhi": "冬至", "xiaohan": "小寒", "dahan": "大寒",
}
SOLAR_TERM_ZH_TO_PINYIN: dict[str, str] = {v: k for k, v in SOLAR_TERM_PINYIN_TO_ZH.items()}

# 星座元素分组：火/土/风/水
ZODIAC_ELEMENTS: dict[str, str] = {
    "aries": "fire", "leo": "fire", "sagittarius": "fire",
    "taurus": "earth", "virgo": "earth", "capricorn": "earth",
    "gemini": "air", "libra": "air", "aquarius": "air",
    "cancer": "water", "scorpio": "water", "pisces": "water",
}

# 各元素对菜 tags 的偏好（命中加分）
ZODIAC_TAG_PREFERENCE: dict[str, tuple[str, ...]] = {
    "fire": ("spicy",),
    "earth": ("easy", "home"),
    "air": ("quick", "easy"),
    "water": ("soup", "nourish", "easy"),
}

# 心情适配规则
MOOD_PREFERENCE: dict[str, dict[str, Any]] = {
    "tired": {"tag": None, "min_protein_g": 8.0, "desc": "高蛋白缓解疲惫"},
    "stressed": {"tag": "soup", "min_protein_g": 0.0, "desc": "暖胃易消化"},
    "anxious": {"tag": None, "min_protein_g": 0.0,
                "ingredients_any": ("鸡蛋", "牛奶", "燕麦", "小米"),
                "desc": "富含色氨酸的食物"},
    "happy": {},
    "neutral": {},
}

# 营养均衡阈值（每 100g）
HIGH_FAT_THRESHOLD = 20.0     # 单菜脂肪 ≥ 20g 视为高脂
HIGH_PROTEIN_THRESHOLD = 12.0 # 单菜蛋白 ≥ 12g 视为高蛋白
LOW_FAT_THRESHOLD = 5.0      # ≤ 5g 视为低脂

# 近 3 天脂肪总和阈值（用于"高脂饮食"判断）
RECENT_HIGH_FAT_TOTAL = 60.0  # 近 3 天选过的菜脂肪总和 ≥ 60g 视为偏油腻


# ---- Weather fallback ----

def _fallback_weather() -> WeatherData:
    """用户未授权位置时的占位天气：温和，不打外部 HTTP。"""
    return WeatherData(
        location_name="未知位置",
        temp_c=22.0,
        feels_like_c=22.0,
        text="温和",
        wind_dir="无",
        wind_scale="0级 无风",
        humidity=50,
        precipitation_mm=0.0,
        weather_tag="mild",
        fetched_at=datetime.now(timezone.utc),
    )


# ---- 硬筛 ----

def _parse_constitution_types(profile: UserProfile | None) -> tuple[str, ...]:
    """profile.constitution_type 用 "qixu;shire" 分号串存，解析成 list。"""
    if profile is None or not profile.constitution_type:
        return ()
    return tuple(p.strip() for p in profile.constitution_type.split(";") if p.strip())


def _is_forbidden(food: Food, profile: UserProfile | None, req: RecommendRequest) -> bool:
    """硬筛判定：菜是否要被剔除。

    触发剔除：
    1. 用户的 forbidden_tags（忌口）∩ food.tags 非空
    2. 用户的体质（主+兼夹）∩ food.forbidden_for_json 非空
    """
    if profile is None:
        return False

    # 1) 忌口：profile.forbidden_tags 与 food.tags 的交集
    forbidden_tags = set(profile.forbidden_tags or [])
    if forbidden_tags:
        food_tags = set(food.tags_json or [])
        if forbidden_tags & food_tags:
            return True

    # 2) 体质禁忌
    user_constitutions = set(_parse_constitution_types(profile))
    if user_constitutions:
        food_forbidden = set(food.forbidden_for_json or [])
        if user_constitutions & food_forbidden:
            return True

    return False


def hard_filter(
    foods: list[Food],
    profile: UserProfile | None,
    req: RecommendRequest,
) -> list[Food]:
    """仅保留有结构化菜谱且通过忌口/体质安全约束的候选。"""
    return [
        food for food in foods
        if food.recipe_ready and not _is_forbidden(food, profile, req)
    ]


# ---- 打分 ----

_MOISTENING_INGREDIENTS = ("银耳", "梨", "百合", "蜂蜜", "雪梨")


def _weather_cold_score(food: Food) -> tuple[float, str]:
    """寒冷天气只做温和加权，避免天气压过所有个性信号。"""
    if food.nature in ("warm", "hot"):
        return 15.0, "天冷温补"
    if food.nature in ("cold", "cool"):
        return 3.0, ""
    return 8.0, ""


def _weather_hot_score(food: Food) -> tuple[float, str]:
    """炎热天气只做温和加权，避免天气压过所有个性信号。"""
    if food.nature in ("cold", "cool"):
        return 15.0, "天热清润"
    if food.nature in ("warm", "hot"):
        return 3.0, ""
    return 8.0, ""


def _score_weather(food: Food, weather: WeatherData) -> tuple[float, str]:
    """天气适配打分（满分 15）。返 (score, reason_phrase or "")。"""
    tag: WeatherTag = weather.weather_tag
    is_soup = food.cooking_method in ("soup", "congee")
    is_moistening = any(
        i in (food.ingredients_json or []) for i in _MOISTENING_INGREDIENTS
    )

    # 表查式：每种天气一个分支，逻辑小而清晰
    if tag == "rainy":
        return (15.0, "雨天暖胃") if is_soup else (8.0, "")
    if tag == "snowy":
        if is_soup or food.nature in ("warm", "hot"):
            return 15.0, "雪天暖性"
        return 6.0, ""
    if tag == "dry":
        return (15.0, "干燥润燥") if is_moistening else (8.0, "")
    if tag == "cold":
        return _weather_cold_score(food)
    if tag == "hot":
        return _weather_hot_score(food)
    # mild 或 any
    return 8.0, ""


def _score_constitution(
    food: Food,
    profile: UserProfile | None,
) -> tuple[float, str]:
    """体质适配打分（满分 10）；信息不足时给中性基准分。"""
    constitutions = set(_parse_constitution_types(profile))
    suitable = set(food.suitable_constitutions_json or [])
    if not constitutions or not suitable:
        return 5.0, ""
    if constitutions & suitable:
        return 10.0, "适合你的体质"
    return 0.0, ""


def _score_activity(food: Food, activity_level: ActivityLevel) -> float:
    """根据活动量做小幅营养偏好调整（满分 5）。"""
    nutrition = food.nutrition_json or {}
    if activity_level == "high":
        protein_g = float(nutrition.get("protein_g", 0.0) or 0.0)
        return 5.0 if protein_g >= HIGH_PROTEIN_THRESHOLD else 0.0
    if activity_level == "light":
        fat_g = float(nutrition.get("fat_g", 0.0) or 0.0)
        return 3.0 if fat_g <= LOW_FAT_THRESHOLD else 0.0
    return 0.0


def _score_method_time(food: Food) -> float:
    """优先省时且相对清爽的做法，合计上限 13 分。"""
    method_score = {
        "steam": 4.0,
        "boil": 4.0,
        "soup": 4.0,
        "congee": 4.0,
        "cold": 3.0,
        "stir_fry": 3.0,
        "stew": 2.0,
        "other": 1.0,
        "deep_fry": 0.0,
    }.get(food.cooking_method, 1.0)
    minutes = food.cooking_time_min or 30
    if minutes <= 20:
        time_score = 9.0
    elif minutes <= 40:
        time_score = 6.0
    elif minutes <= 60:
        time_score = 4.0
    else:
        time_score = 2.0
    return min(float(RULE_V3_WEIGHTS["method_time"]), method_score + time_score)


def _scale_score(raw: float, raw_max: float, dimension: str) -> float:
    cap = float(RULE_V3_WEIGHTS[dimension])
    return round(max(0.0, min(raw_max, raw)) / raw_max * cap, 2)


def _score_solar_term(food: Food, today: TodayContext) -> tuple[float, str]:
    """节气适配打分（满分 15）。

    food.seasonal_solar_terms 用拼音键存；today 返中文 → 转拼音比较。
    """
    food_terms = set(food.seasonal_solar_terms_json or [])
    if not food_terms:
        return 0.0, ""

    # 当前节气（仅节气当天有值）
    if today.solar_term_current:
        current_pinyin = SOLAR_TERM_ZH_TO_PINYIN.get(today.solar_term_current, "")
        if current_pinyin and current_pinyin in food_terms:
            return 15.0, f"正值{today.solar_term_current}"

    # 下一节气
    next_pinyin = SOLAR_TERM_ZH_TO_PINYIN.get(today.solar_term_next_name, "")
    if next_pinyin and next_pinyin in food_terms:
        return 8.0, f"临近{today.solar_term_next_name}"

    return 0.0, ""


def _score_zodiac(food: Food, today: TodayContext) -> tuple[float, str]:
    """星座趣味打分（满分 3）。仅彩蛋。"""
    element = ZODIAC_ELEMENTS.get(today.zodiac_sign, "")
    preferred = ZODIAC_TAG_PREFERENCE.get(element, ())
    if not preferred:
        return 0.0, ""
    food_tags = set(food.tags_json or [])
    matched = food_tags & set(preferred)
    if matched:
        return 3.0, ""
    return 0.0, ""


def _score_mood(food: Food, mood: Mood) -> tuple[float, str]:
    """心情适配打分（满分 12）。命中任一规则即得分。"""
    pref = MOOD_PREFERENCE.get(mood, {})
    if not pref:
        return 0.0, ""

    nutrition = food.nutrition_json or {}
    protein_g = float(nutrition.get("protein_g", 0.0) or 0.0)

    hit = False
    # 高蛋白（tired）
    min_protein = pref.get("min_protein_g", 0.0)
    if min_protein and protein_g >= min_protein:
        hit = True

    # 暖胃（stressed → soup/congee cooking_method）
    if pref.get("tag") == "soup" and food.cooking_method in ("soup", "congee"):
        hit = True

    # 色氨酸食材（anxious）
    target_ingredients = pref.get("ingredients_any")
    if target_ingredients:
        if any(ing in (food.ingredients_json or []) for ing in target_ingredients):
            hit = True

    desc = pref.get("desc", "")
    return (12.0, str(desc)) if hit else (0.0, "")


def _score_nutrition_balance_with_foods(
    food: Food,
    history: list[DailyLog],
    all_foods: list[Food],
) -> tuple[float, str]:
    """营养均衡打分（满分 15）— 用全量 foods 反查历史菜的脂肪。

    简化策略：
    - 历史 chosen 数 < 1 → 默认 8
    - 历史 3 天脂肪总和 ≥ RECENT_HIGH_FAT_TOTAL → 低脂菜 +15
    - 否则 → 默认 8
    """
    chosen_ids: list[int] = []
    for log in history:
        chosen_ids.extend(log.chosen_food_ids_json or [])
    if not chosen_ids:
        return 8.0, ""

    foods_by_id: dict[int, Food] = {f.id: f for f in all_foods if f.id is not None}
    total_fat = 0.0
    for fid in chosen_ids:
        f = foods_by_id.get(fid)
        if f is None or not f.nutrition_json:
            continue
        total_fat += float(f.nutrition_json.get("fat_g", 0.0) or 0.0)

    food_fat = float((food.nutrition_json or {}).get("fat_g", 0.0) or 0.0)

    if total_fat >= RECENT_HIGH_FAT_TOTAL and food_fat <= LOW_FAT_THRESHOLD:
        return 15.0, "与你近三天偏油腻饮食互补"
    return 8.0, ""


def _score_food(
    food: Food,
    weather: WeatherData,
    today: TodayContext,
    profile: UserProfile | None,
    history: list[DailyLog],
    all_foods: list[Food],
    mood: Mood,
    activity_level: ActivityLevel,
) -> RankedCandidate:
    """计算单道菜的 75 分规则分项和解释短语。"""
    w_score, w_phrase = _score_weather(food, weather)
    s_score, s_phrase = _score_solar_term(food, today)
    z_score, z_phrase = _score_zodiac(food, today)
    m_score, m_phrase = _score_mood(food, mood)
    n_score, n_phrase = _score_nutrition_balance_with_foods(food, history, all_foods)
    c_score, c_phrase = _score_constitution(food, profile)
    a_score = _score_activity(food, activity_level)
    breakdown = ScoreBreakdown(
        weather=_scale_score(w_score, 15.0, "weather"),
        solar_term=_scale_score(s_score, 15.0, "solar_term"),
        mood=_scale_score(m_score, 12.0, "mood"),
        nutrition=_scale_score(n_score, 15.0, "nutrition"),
        constitution=_scale_score(c_score, 10.0, "constitution"),
        activity=_scale_score(a_score, 5.0, "activity"),
        zodiac=_scale_score(z_score, 3.0, "zodiac"),
        method_time=_score_method_time(food),
    )
    return RankedCandidate(
        food=food,
        base_score=breakdown.total,
        breakdown=breakdown,
        reason_phrases={
            "weather": w_phrase,
            "solar_term": s_phrase,
            "zodiac": z_phrase,
            "mood": m_phrase,
            "nutrition": n_phrase,
            "constitution": c_phrase,
        },
    )


# ---- 理由生成 ----

def _make_reason(phrases: dict[str, str], food: Food, mood: Mood) -> str:
    """把命中短语组合成自然语言理由。

    模板：「适合今日【{weather}】场景，{solar_term}{zodiac}{mood}{nutrition}。」
    仅出现命中的维度；都未命中兜底「今天品尝舒适」。
    """
    parts: list[str] = []
    weather_phrase = phrases.get("weather", "")
    if weather_phrase:
        parts.append(weather_phrase)
    solar_phrase = phrases.get("solar_term", "")
    if solar_phrase:
        parts.append(solar_phrase)
    mood_phrase = phrases.get("mood", "")
    if mood_phrase:
        parts.append(mood_phrase)
    nutrition_phrase = phrases.get("nutrition", "")
    if nutrition_phrase:
        parts.append(nutrition_phrase)
    constitution_phrase = phrases.get("constitution", "")
    if constitution_phrase:
        parts.append(constitution_phrase)

    if not parts:
        return f"今天品尝{food.name}很合适"

    # 拼接：前半句「适合今日【{parts joined}】场景」
    scene = "、".join(parts)
    return f"适合今日【{scene}】场景，{food.name}正合时令"


def _build_complete_meal(
    session: Session,
    candidates: list[RankedCandidate],
    ranking_history: RecommendationHistory,
    mood: Mood,
) -> tuple[MealBuildResult, list[RankedCandidate]]:
    fresh_candidates: list[RankedCandidate] = []
    for meal_role in ("main", "vegetable", "staple"):
        role_candidates = [
            candidate for candidate in candidates
            if candidate.food.meal_role == meal_role
        ]
        fresh_candidates.extend(
            apply_novelty(role_candidates, ranking_history, top_n=1)
        )

    recipes_by_food_id = {
        recipe.food_id: recipe
        for recipe in session.exec(select(Recipe)).all()
    }
    meal_candidates = [
        MealCandidate(
            ranked=candidate,
            recipe=recipes_by_food_id[candidate.food.id],
            reason=candidate.rerank_reason or _make_reason(
                dict(candidate.reason_phrases),
                candidate.food,
                mood,
            ),
        )
        for candidate in fresh_candidates
        if candidate.food.id in recipes_by_food_id
    ]
    try:
        return build_meal(meal_candidates), fresh_candidates
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


# ---- 主入口 ----

async def recommend(
    session: Session,
    user: User,
    req: RecommendRequest,
    *,
    reranker: CandidateReranker | None = None,
) -> RecommendResponse:
    """硬过滤后依次执行规则评分、有界重排、新鲜度和多样性选择。"""
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    if profile_service.get_profile(session, user.id) is None:
        raise NotFoundError("user_profile", user.id)
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == user.id)
    ).first()
    if profile is None:  # pragma: no cover
        raise NotFoundError("user_profile", user.id)

    weather = (
        await weather_client.get_current(req.lat, req.lng)
        if req.lat is not None and req.lng is not None
        else _fallback_weather()
    )
    today_context = get_today_context_cached()
    today = date.today()
    history_7d = daily_service.get_recent(session, user.id, days=7)
    nutrition_start = today - timedelta(days=2)
    nutrition_history = [
        record for record in history_7d
        if record.log_date >= nutrition_start
    ]
    events_7d = daily_service.get_recent_recommendation_events(
        session,
        user.id,
        days=7,
        as_of=today,
    )
    foods, _ = food_service.get_all(session, page=1, size=500)
    kept = hard_filter(foods, profile, req)
    if not kept:
        raise ValidationError("没有可选菜（全部被忌口/体质禁忌过滤）")

    candidates = [
        _score_food(
            food,
            weather,
            today_context,
            profile,
            nutrition_history,
            foods,
            req.mood,
            req.activity_level,
        )
        for food in kept
    ]
    active_reranker = reranker or IdentityReranker()
    ranking_context = RecommendationRankingContext(
        mood=req.mood,
        activity_level=req.activity_level,
        weather_tag=weather.weather_tag,
        solar_term=(
            today_context.solar_term_current
            or today_context.solar_term_next_name
        ),
        constitution_types=_parse_constitution_types(profile),
    )
    try:
        adjustments = await active_reranker.rerank(candidates, ranking_context)
        candidates = apply_rerank_adjustments(candidates, adjustments)
        engine_name = active_reranker.engine_name
    except Exception as exc:
        log.warning(
            "recommend_reranker_fallback",
            user_id=user.id,
            reranker=active_reranker.engine_name,
            error_type=type(exc).__name__,
        )
        engine_name = "rules_v3"

    ranking_history = build_recommendation_history(
        history_7d,
        events_7d,
        as_of=today,
    )
    meal, fresh_candidates = _build_complete_meal(
        session,
        candidates,
        ranking_history,
        req.mood,
    )

    rec_ids = [item.food_id for item in meal.primary_meal.items]
    _, event = daily_service.record_recommendation(
        session,
        user.id,
        recommended_food_ids=rec_ids,
        mood=req.mood,
        activity_level=req.activity_level,
        weather_tag=weather.weather_tag,
        engine=engine_name,
        event_date=today,
    )

    candidates_by_id = {
        candidate.food.id: candidate
        for candidate in fresh_candidates
        if candidate.food.id is not None
    }
    response_foods: list[FoodWithReason] = []
    for food_id in rec_ids:
        candidate = candidates_by_id[food_id]
        data = candidate.food.to_read_dict()
        data["reason"] = candidate.rerank_reason or _make_reason(
            dict(candidate.reason_phrases),
            candidate.food,
            req.mood,
        )
        data["score"] = candidate.normalized_score
        response_foods.append(FoodWithReason(**data))

    log.info(
        "recommend_ok",
        user_id=user.id,
        event_id=event.id,
        engine=engine_name,
        weather_tag=weather.weather_tag,
        seen_today_count=len(ranking_history.seen_today),
        history_chosen_count=len(ranking_history.chosen_days_ago),
        recommended_food_ids=rec_ids,
    )
    return RecommendResponse(
        foods=response_foods,
        recommendation_id=event.id or 0,
        primary_meal=meal.primary_meal,
        substitutions=meal.substitutions,
        substitution_notice=meal.substitution_notice,
        engine=engine_name,
        context=RecommendContext(weather=weather, today=today_context),
    )


__all__ = [
    "MOOD_PREFERENCE",
    "SOLAR_TERM_PINYIN_TO_ZH",
    "SOLAR_TERM_ZH_TO_PINYIN",
    "ZODIAC_ELEMENTS",
    "ZODIAC_TAG_PREFERENCE",
    "recommend",
]
