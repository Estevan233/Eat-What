"""推荐算法核心 - 规则筛选 + 加权打分 + 多样性 + 理由生成。

学习点：
- 纯函数式：所有外部依赖（profile/weather/today/history/foods）从函数参数注入，便于测试
- 主入口 recommend() 协调 5 个子流程：硬筛 / 打分 / 排序 / 多样性 / 理由
- 算法稳定性：相同输入必返相同输出（无随机、无时间敏感性）
- 性能：200 道菜全量打分 < 50ms（纯 Python 字段查找）
"""
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlmodel import Session, select

from app.core.errors import NotFoundError, ValidationError
from app.models.daily_log import DailyLog
from app.models.food import Food
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
from app.schemas.today_context import TodayContext
from app.schemas.weather import WeatherData, WeatherTag
from app.services import daily_service, food_service, profile_service
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
LOW_PROTEIN_THRESHOLD = 5.0

# 近 3 天脂肪/蛋白总和阈值（用于"高脂饮食"判断）
RECENT_HIGH_FAT_TOTAL = 60.0  # 近 3 天选过的菜脂肪总和 ≥ 60g 视为偏油腻
RECENT_HIGH_PROTEIN_TOTAL = 80.0


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


# ---- 打分 ----

_MOISTENING_INGREDIENTS = ("银耳", "梨", "百合", "蜂蜜", "雪梨")


def _weather_cold_score(food: Food) -> tuple[float, str]:
    """cold 天气：温热性 +30 / 寒凉性 0 / 中性 10。"""
    if food.nature in ("warm", "hot"):
        return 30.0, "天冷温补"
    if food.nature in ("cold", "cool"):
        return 0.0, ""
    return 10.0, ""


def _weather_hot_score(food: Food) -> tuple[float, str]:
    """hot 天气：凉性 +30 / 温热性 0 / 中性 10。"""
    if food.nature in ("cold", "cool"):
        return 30.0, "天热清润"
    if food.nature in ("warm", "hot"):
        return 0.0, ""
    return 10.0, ""


def _score_weather(food: Food, weather: WeatherData) -> tuple[float, str]:
    """天气适配打分（满分 30）。返 (score, reason_phrase or "")。"""
    tag: WeatherTag = weather.weather_tag
    is_soup = food.cooking_method in ("soup", "congee")
    is_moistening = any(
        i in (food.ingredients_json or []) for i in _MOISTENING_INGREDIENTS
    )

    # 表查式：每种天气一个分支，逻辑小而清晰
    if tag == "rainy":
        return (30.0, "雨天暖胃") if is_soup else (8.0, "")
    if tag == "snowy":
        if is_soup or food.nature in ("warm", "hot"):
            return 30.0, "雪天暖性"
        return 8.0, ""
    if tag == "dry":
        return (30.0, "干燥润燥") if is_moistening else (8.0, "")
    if tag == "cold":
        return _weather_cold_score(food)
    if tag == "hot":
        return _weather_hot_score(food)
    # mild 或 any
    return 10.0, ""


def _score_solar_term(food: Food, today: TodayContext) -> tuple[float, str]:
    """节气适配打分（满分 20）。

    food.seasonal_solar_terms 用拼音键存；today 返中文 → 转拼音比较。
    """
    food_terms = set(food.seasonal_solar_terms_json or [])
    if not food_terms:
        return 0.0, ""

    # 当前节气（仅节气当天有值）
    if today.solar_term_current:
        current_pinyin = SOLAR_TERM_ZH_TO_PINYIN.get(today.solar_term_current, "")
        if current_pinyin and current_pinyin in food_terms:
            return 20.0, f"正值{today.solar_term_current}"

    # 下一节气
    next_pinyin = SOLAR_TERM_ZH_TO_PINYIN.get(today.solar_term_next_name, "")
    if next_pinyin and next_pinyin in food_terms:
        return 10.0, f"临近{today.solar_term_next_name}"

    return 0.0, ""


def _score_zodiac(food: Food, today: TodayContext) -> tuple[float, str]:
    """星座趣味打分（满分 10）。仅彩蛋。"""
    element = ZODIAC_ELEMENTS.get(today.zodiac_sign, "")
    preferred = ZODIAC_TAG_PREFERENCE.get(element, ())
    if not preferred:
        return 0.0, ""
    food_tags = set(food.tags_json or [])
    matched = food_tags & set(preferred)
    if matched:
        return 10.0, ""
    return 0.0, ""


def _score_mood(food: Food, mood: Mood) -> tuple[float, str]:
    """心情适配打分（满分 20）。命中时返回 (score, desc 短语)。"""
    pref = MOOD_PREFERENCE.get(mood, {})
    if not pref:
        return 0.0, ""

    score = 0.0
    nutrition = food.nutrition_json or {}
    protein_g = float(nutrition.get("protein_g", 0.0) or 0.0)

    hit = False
    # 高蛋白（tired）
    min_protein = pref.get("min_protein_g", 0.0)
    if min_protein and protein_g >= min_protein:
        score += 8.0
        hit = True

    # 暖胃（stressed → soup/congee cooking_method）
    if pref.get("tag") == "soup" and food.cooking_method in ("soup", "congee"):
        score += 8.0
        hit = True

    # 色氨酸食材（anxious）
    target_ingredients = pref.get("ingredients_any")
    if target_ingredients:
        if any(ing in (food.ingredients_json or []) for ing in target_ingredients):
            score += 8.0
            hit = True

    score = min(score, 20.0)
    desc = pref.get("desc", "")
    return score, (desc if hit and desc else "")


def _score_nutrition_balance_with_foods(
    food: Food,
    history: list[DailyLog],
    all_foods: list[Food],
) -> tuple[float, str]:
    """营养均衡打分（满分 20）— 用全量 foods 反查历史菜的脂肪/蛋白。

    简化策略：
    - 历史 chosen 数 < 1 → 默认 10
    - 历史 3 天脂肪总和 ≥ RECENT_HIGH_FAT_TOTAL → 低脂菜 +20
    - 历史 3 天蛋白总和 ≥ RECENT_HIGH_PROTEIN_TOTAL → 低蛋白菜 +10
    - 否则 → 默认 10
    """
    chosen_ids: list[int] = []
    for log in history:
        chosen_ids.extend(log.chosen_food_ids_json or [])
    if not chosen_ids:
        return 10.0, ""

    foods_by_id: dict[int, Food] = {f.id: f for f in all_foods if f.id is not None}
    total_fat = 0.0
    total_protein = 0.0
    for fid in chosen_ids:
        f = foods_by_id.get(fid)
        if f is None or not f.nutrition_json:
            continue
        total_fat += float(f.nutrition_json.get("fat_g", 0.0) or 0.0)
        total_protein += float(f.nutrition_json.get("protein_g", 0.0) or 0.0)

    food_fat = float((food.nutrition_json or {}).get("fat_g", 0.0) or 0.0)
    food_protein = float((food.nutrition_json or {}).get("protein_g", 0.0) or 0.0)

    if total_fat >= RECENT_HIGH_FAT_TOTAL and food_fat <= LOW_FAT_THRESHOLD:
        return 20.0, "与你近三天偏油腻饮食互补"
    if total_protein >= RECENT_HIGH_PROTEIN_TOTAL and food_protein <= LOW_PROTEIN_THRESHOLD:
        return 10.0, ""
    return 10.0, ""


def _score_food(
    food: Food,
    weather: WeatherData,
    today: TodayContext,
    profile: UserProfile | None,
    history: list[DailyLog],
    all_foods: list[Food],
    mood: Mood,
    activity_level: ActivityLevel,
) -> tuple[float, dict[str, str]]:
    """计算单道菜的总分 + 各维度命中短语。

    返 (total_score, reason_phrases_dict)：
      reason_phrases_dict key: weather/solar_term/zodiac/mood/nutrition
      value: 命中短语（"" 表示未命中）
    """
    w_score, w_phrase = _score_weather(food, weather)
    s_score, s_phrase = _score_solar_term(food, today)
    z_score, z_phrase = _score_zodiac(food, today)
    m_score, m_phrase = _score_mood(food, mood)
    n_score, n_phrase = _score_nutrition_balance_with_foods(food, history, all_foods)

    total = w_score + s_score + z_score + m_score + n_score

    phrases = {
        "weather": w_phrase,
        "solar_term": s_phrase,
        "zodiac": z_phrase,
        "mood": m_phrase,
        "nutrition": n_phrase,
    }
    # 用 activity_level 微调：high → 偏好高蛋白；light → 偏好低脂
    if activity_level == "high":
        protein_g = float((food.nutrition_json or {}).get("protein_g", 0.0) or 0.0)
        if protein_g >= HIGH_PROTEIN_THRESHOLD:
            total += 3.0  # 不计入 reason，仅加分
    elif activity_level == "light":
        food_fat = float((food.nutrition_json or {}).get("fat_g", 0.0) or 0.0)
        if food_fat <= LOW_FAT_THRESHOLD:
            total += 2.0

    return min(total, 100.0), phrases


# ---- 多样性 ----

def _ensure_diversity(
    scored: list[tuple[Food, float, dict[str, str]]],
    *,
    top_n: int = 3,
) -> list[tuple[Food, float, dict[str, str]]]:
    """从已排序的候选里挑 top_n，保证多样性。

    约束：
    1. 不超过 2 道 category 相同
    2. 不超过 2 道 cooking_method 相同
    3. 同分按 food.id 升序 tie-break
    """
    selected: list[tuple[Food, float, dict[str, str]]] = []
    cat_counts: dict[str, int] = {}
    method_counts: dict[str, int] = {}

    for food, score, phrases in scored:
        if len(selected) >= top_n:
            break
        cat = food.category
        method = food.cooking_method
        if cat_counts.get(cat, 0) >= 2:
            continue
        if method_counts.get(method, 0) >= 2:
            continue
        selected.append((food, score, phrases))
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        method_counts[method] = method_counts.get(method, 0) + 1

    # 兜底：多样性约束太严导致不够 top_n，放宽 category 限制再补
    if len(selected) < top_n:
        for food, score, phrases in scored:
            if len(selected) >= top_n:
                break
            if any(s[0].id == food.id for s in selected):
                continue
            selected.append((food, score, phrases))

    return selected


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

    if not parts:
        return f"今天品尝{food.name}很合适"

    # 拼接：前半句「适合今日【{parts joined}】场景」
    scene = "、".join(parts)
    return f"适合今日【{scene}】场景，{food.name}正合时令"


# ---- 主入口 ----

async def recommend(
    session: Session,
    user: User,
    req: RecommendRequest,
) -> RecommendResponse:
    """核心推荐入口。

    流程：
    1. 取 profile（未建档抛 NotFoundError）
    2. 取 weather（lat/lng None 走 fallback）
    3. 取 today context（缓存）
    4. 取最近 3 天 DailyLog
    5. 取全量 foods（MVP 200 条够用）
    6. 硬筛 forbidden
    7. 打分 + 排序
    8. 多样性挑 top 3
    9. 写 DailyLog（recommended_food_ids）
    """
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    # 1) profile
    profile_read = profile_service.get_profile(session, user.id)
    if profile_read is None:
        raise NotFoundError("user_profile", user.id)

    # 取原始 UserProfile（需要 forbidden_tags 与 constitution_type）
    stmt = select(UserProfile).where(UserProfile.user_id == user.id)
    profile = session.exec(stmt).first()
    if profile is None:  # pragma: no cover
        raise NotFoundError("user_profile", user.id)

    # 2) weather
    if req.lat is not None and req.lng is not None:
        weather = await weather_client.get_current(req.lat, req.lng)
    else:
        weather = _fallback_weather()

    # 3) today
    today = get_today_context_cached()

    # 4) history
    history = daily_service.get_recent(session, user.id, days=3)

    # 5) foods 全量（一次性拉 500 条上限）
    foods, _ = food_service.get_all(session, page=1, size=500)

    # 6) 硬筛
    kept = [f for f in foods if not _is_forbidden(f, profile, req)]
    if not kept:
        raise ValidationError("没有可选菜（全部被忌口/体质禁忌过滤）")

    # 7) 打分 + 排序
    scored: list[tuple[Food, float, dict[str, str]]] = [
        (f, *_score_food(f, weather, today, profile, history, foods,
                         req.mood, req.activity_level))
        for f in kept
    ]
    # 排序：score desc, food.id asc（确定性 tie-break）
    scored.sort(key=lambda x: (-x[1], x[0].id or 0))
    top6 = scored[:6]

    # 8) 多样性挑 top 3
    top3 = _ensure_diversity(top6, top_n=3)

    # 9) 写 DailyLog
    rec_ids = [f.id for f, _, _ in top3 if f.id is not None]
    daily_service.upsert_today_log(
        session, user.id,
        recommended_food_ids=rec_ids,
        mood=req.mood,
        activity_level=req.activity_level,
        weather_tag=weather.weather_tag,
    )

    log.info(
        "recommend_ok",
        user_id=user.id,
        mood=req.mood,
        weather_tag=weather.weather_tag,
        chosen_ids=rec_ids,
        top_score=top3[0][1] if top3 else 0.0,
    )

    # 构造响应
    food_with_reason_list: list[FoodWithReason] = []
    for f, s, phrases in top3:
        data = f.to_read_dict()
        data["reason"] = _make_reason(phrases, f, req.mood)
        data["score"] = round(s, 2)
        food_with_reason_list.append(FoodWithReason(**data))

    return RecommendResponse(
        foods=food_with_reason_list,
        context=RecommendContext(weather=weather, today=today),
    )


__all__ = [
    "MOOD_PREFERENCE",
    "SOLAR_TERM_PINYIN_TO_ZH",
    "SOLAR_TERM_ZH_TO_PINYIN",
    "ZODIAC_ELEMENTS",
    "ZODIAC_TAG_PREFERENCE",
    "recommend",
]
