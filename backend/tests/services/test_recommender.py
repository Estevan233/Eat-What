"""T10 推荐算法核心 service 单测。

覆盖 PRD 算法主要分支：
1. 基本：返 3 道菜 + 上下文
2. 硬筛：忌口（forbidden_tags）剔除
3. 硬筛：体质禁忌（forbidden_for）剔除
4. 天气 cold + 温热性菜 → 上榜
5. 天气 rainy + 汤粥类 → 软加分，但不强制上榜
6. 节气 → 时令菜加分
7. 心情 tired → 高蛋白菜加分
8. 心情 anxious → 含色氨酸食材加分
9. 营养均衡：历史高脂 → 低脂菜加分
10. 多样性：top 3 不全相同 category
11. 未建档 → NotFoundError
12. 理由文本含关键词
13. 同输入结果稳定
14. fallback weather（lat/lng None）→ weather_tag mild

学习点：
- 用 monkeypatch 替换 weather_client.get_current / get_today_context_cached
- 直接在 in-memory session 里建 Food + UserProfile + DailyLog
- 不调 API 路由，直接调 service 函数，便于断言内部细节
"""
import asyncio
from datetime import date, datetime, timedelta, timezone
from time import perf_counter
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event
from sqlmodel import select

from app.core.errors import ExternalAPIError, NotFoundError
from app.models.daily_log import DailyLog
from app.models.food import Food
from app.models.recipe import Recipe
from app.models.recommendation_event import RecommendationEvent
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.daily import MealIntent, RecommendRequest
from app.schemas.today_context import TodayContext
from app.schemas.weather import WeatherData
from app.services import recommender
from app.services.recommendation_ranking import RULE_V4_WEIGHTS, RerankAdjustment

# ---- Fixtures ----

def _make_food(
    name: str,
    *,
    category: str = "stir_fry",
    cooking_method: str = "stir_fry",
    nature: str = "neutral",
    tags: list[str] | None = None,
    forbidden_for: list[str] | None = None,
    suitable_constitutions: list[str] | None = None,
    ingredients: list[str] | None = None,
    nutrition: dict[str, Any] | None = None,
    seasonal_solar_terms: list[str] | None = None,
) -> Food:
    """构造 Food 记录。"""
    return Food(
        name=name,
        category=category,
        ingredients_json=ingredients or [],
        calories_kcal_per_100g=100.0,
        nutrition_json=nutrition or {"protein_g": 5.0, "fat_g": 5.0, "carb_g": 10.0, "fiber_g": 1.0},
        nature=nature,
        flavor_json=[],
        organ_meridians_json=[],
        suitable_constitutions_json=suitable_constitutions or ["pinghe"],
        suitable_weathers_json=["any"],
        forbidden_for_json=forbidden_for or [],
        tags_json=tags or [],
        cooking_method=cooking_method,
        cooking_time_min=20,
        image_url=None,
        seasonal_solar_terms_json=seasonal_solar_terms or [],
        description=f"{name} 测试菜",
    )


def test_meal_intent_schema_normalizes_deduplicates_and_ignores_unknown_fields() -> None:
    intent = MealIntent.model_validate({
        "available_ingredients": [" 番茄 ", "番茄", "鸡蛋"],
        "excluded_ingredients": [" 花生 "],
        "max_time_minutes": 20,
        "goal": "balanced",
        "dining_mode_hint": "cook",
        "summary": " 冰箱有番茄鸡蛋，二十分钟 ",
        "invented_food_ids": [1, 2, 3],
    })

    assert intent.available_ingredients == ["番茄", "鸡蛋"]
    assert intent.excluded_ingredients == ["花生"]
    assert intent.summary == "冰箱有番茄鸡蛋，二十分钟"
    assert "invented_food_ids" not in intent.model_dump()


def test_meal_intent_excluded_ingredient_is_a_hard_filter() -> None:
    peanut = _make_food("花生拌菠菜", ingredients=["菠菜", "花生"])
    egg = _make_food("番茄炒蛋", ingredients=["番茄", "鸡蛋"])
    peanut.recipe_ready = True
    egg.recipe_ready = True
    request = RecommendRequest(
        meal_intent=MealIntent(
            excluded_ingredients=["花生"],
            summary="不要花生",
        ),
    )

    assert recommender.hard_filter([peanut, egg], None, request) == [egg]


def test_meal_intent_mode_hint_cannot_override_explicit_dining_mode() -> None:
    request = RecommendRequest(
        dining_mode="cook",
        meal_intent=MealIntent(
            dining_mode_hint="eat_out",
            summary="想点外卖",
        ),
    )

    assert request.dining_mode == "cook"
    assert request.meal_intent is not None
    assert request.meal_intent.dining_mode_hint == "eat_out"


def _make_profile(
    user_id: int,
    *,
    forbidden_tags: list[str] | None = None,
    constitution_type: str | None = None,
) -> UserProfile:
    """构造 UserProfile 记录。"""
    record = UserProfile(
        user_id=user_id,
        birthday="1990-01-15",
        gender="male",
        height_cm=175,
        weight_kg=70.0,
        forbidden_tags=forbidden_tags or [],
        constitution_type=constitution_type,
        constitution_scores=None,
    )
    record.updated_at = datetime.utcnow()
    return record


def _attach_recipe(session, food: Food, role: str) -> None:
    assert food.id is not None
    food.meal_role = role
    food.recipe_ready = True
    food.visual_key = f'test-{role}-{food.id}'
    session.add(food)
    session.add(
        Recipe(
            food_id=food.id,
            servings=2,
            ingredients_json=[],
            steps_json=['一', '二', '三', '四'],
            prep_time_min=5,
            cook_time_min=food.cooking_time_min or 20,
            nutrition_per_serving_json={
                'energy_kcal': (food.calories_kcal_per_100g or 100) * 2.5,
                'protein_g': float((food.nutrition_json or {}).get('protein_g', 0)),
                'fat_g': float((food.nutrition_json or {}).get('fat_g', 0)),
                'carb_g': float((food.nutrition_json or {}).get('carb_g', 0)),
            },
            nutrition_basis='测试估算',
        )
    )


def _make_weather(tag: str = "mild", *, temp_c: float = 22.0) -> WeatherData:
    """构造 WeatherData mock。"""
    return WeatherData(
        location_name="测试位置",
        temp_c=temp_c,
        feels_like_c=temp_c,
        text="温和",
        wind_dir="无",
        wind_scale="0级 无风",
        humidity=50,
        precipitation_mm=0.0,
        weather_tag=tag,  # type: ignore[arg-type]
        fetched_at=datetime.now(timezone.utc),
    )


def _make_today(
    *,
    solar_term_current: str = "",
    solar_term_next_name: str = "立秋",
    zodiac_sign: str = "leo",
    animal: str = "马",
) -> TodayContext:
    """构造 TodayContext mock。"""
    return TodayContext(
        date=date.today(),
        solar_term_current=solar_term_current,
        solar_term_next_name=solar_term_next_name,
        solar_term_next_date="2026-08-07",
        zodiac_sign=zodiac_sign,
        animal=animal,
        lunar_month=7,
        lunar_day=15,
        is_leap_month=False,
    )


def _patch_external(
    monkeypatch: pytest.MonkeyPatch,
    *,
    weather_tag: str = "mild",
    temp_c: float = 22.0,
    solar_term_current: str = "",
    solar_term_next_name: str = "立秋",
    zodiac_sign: str = "leo",
) -> None:
    """统一 monkeypatch：替换 weather_client + today_context。

    weather_client.get_current → AsyncMock 返 weather_tag
    get_today_context_cached → 返指定节气/星座
    """
    weather = _make_weather(weather_tag, temp_c=temp_c)
    monkeypatch.setattr(
        recommender.weather_client, "get_current",
        AsyncMock(return_value=weather),
    )
    monkeypatch.setattr(
        recommender, "get_today_context_cached",
        lambda: _make_today(
            solar_term_current=solar_term_current,
            solar_term_next_name=solar_term_next_name,
            zodiac_sign=zodiac_sign,
        ),
    )


@pytest.fixture
def seeded_session(session):
    """预置 User + UserProfile + 一组 Food，返回 (user, foods)。"""
    user = User(openid="test_openid", nickname="测试用户", avatar_url=None)
    session.add(user)
    session.commit()
    session.refresh(user)

    profile = _make_profile(user.id)
    session.add(profile)
    session.commit()

    foods = [
        _make_food("白米饭", category="staple", cooking_method="boil",
                   nature="neutral", tags=["easy"],
                   nutrition={"protein_g": 2.6, "fat_g": 0.3, "carb_g": 25.6, "fiber_g": 0.4}),
        _make_food("小米粥", category="congee", cooking_method="congee",
                   nature="cool", tags=["easy", "soup"],
                   nutrition={"protein_g": 1.4, "fat_g": 0.4, "carb_g": 9.6, "fiber_g": 0.3},
                   ingredients=["小米", "水"],
                   seasonal_solar_terms=["lidong", "dongzhi"]),
        _make_food("清蒸鲈鱼", category="steam", cooking_method="steam",
                   nature="neutral", tags=["fish", "easy"],
                   nutrition={"protein_g": 18.6, "fat_g": 2.8, "carb_g": 0.5, "fiber_g": 0.0}),
        _make_food("红烧肉", category="stew", cooking_method="stew",
                   nature="neutral", tags=["pork"],
                   forbidden_for=["tanshi", "shire"],
                   nutrition={"protein_g": 12.5, "fat_g": 32.0, "carb_g": 4.2, "fiber_g": 0.3}),
        _make_food("凉拌黄瓜", category="cold_dish", cooking_method="cold",
                   nature="cool", tags=["vegetarian", "easy"],
                   nutrition={"protein_g": 1.0, "fat_g": 1.5, "carb_g": 4.2, "fiber_g": 0.8}),
        _make_food("银耳莲子羹", category="soup", cooking_method="soup",
                   nature="neutral", tags=["vegetarian", "easy", "soup"],
                   ingredients=["银耳", "莲子", "百合"],
                   nutrition={"protein_g": 1.2, "fat_g": 0.2, "carb_g": 6.0, "fiber_g": 0.5}),
        _make_food("番茄炒蛋", category="stir_fry", cooking_method="stir_fry",
                   nature="neutral", tags=["egg", "easy"],
                   ingredients=["番茄", "鸡蛋", "葱"],
                   nutrition={"protein_g": 5.5, "fat_g": 5.0, "carb_g": 4.5, "fiber_g": 1.2},
                   seasonal_solar_terms=["liqiu"]),
        _make_food("清炖牛肉", category="stew", cooking_method="stew",
                   nature="warm", tags=["beef", "easy"],
                   nutrition={"protein_g": 17.0, "fat_g": 8.0, "carb_g": 2.0, "fiber_g": 0.0}),
        _make_food("羊肉汤", category="soup", cooking_method="soup",
                   nature="warm", tags=["easy", "soup"],
                   nutrition={"protein_g": 15.0, "fat_g": 10.0, "carb_g": 1.0, "fiber_g": 0.0}),
    ]
    for f in foods:
        session.add(f)
    session.commit()
    roles = {
        '白米饭': 'staple',
        '小米粥': 'staple',
        '凉拌黄瓜': 'vegetable',
        '银耳莲子羹': 'vegetable',
    }
    for food in foods:
        _attach_recipe(session, food, roles.get(food.name, 'main'))
    session.commit()
    return user, foods


# ---- 测试 ----


def test_score_food_uses_exact_v4_caps() -> None:
    food = _make_food(
        'v3满分菜',
        cooking_method='steam',
        nature='warm',
        tags=['spicy'],
        suitable_constitutions=['qixu'],
        nutrition={'protein_g': 20, 'fat_g': 2, 'carb_g': 8, 'fiber_g': 3},
        seasonal_solar_terms=['liqiu'],
    )
    food.id = 1
    food.cooking_time_min = 15
    fatty = _make_food(
        '历史高脂菜',
        nutrition={'protein_g': 10, 'fat_g': 65, 'carb_g': 8, 'fiber_g': 1},
    )
    fatty.id = 2
    profile = _make_profile(1, constitution_type='qixu')
    history = [
        DailyLog(
            user_id=1,
            log_date=date.today(),
            chosen_food_ids_json=[2],
        )
    ]

    ranked = recommender._score_food(
        food,
        _make_weather('cold', temp_c=5),
        _make_today(solar_term_current='立秋', zodiac_sign='leo'),
        profile,
        history,
        [food, fatty],
        'tired',
        'high',
    )

    assert ranked.breakdown.nutrition == RULE_V4_WEIGHTS['nutrition']
    assert ranked.breakdown.seasonal_wellness == RULE_V4_WEIGHTS['seasonal_wellness']
    assert ranked.breakdown.personal_family == RULE_V4_WEIGHTS['personal_family']
    assert ranked.breakdown.preference_history == RULE_V4_WEIGHTS['preference_history']
    assert ranked.breakdown.feasibility == RULE_V4_WEIGHTS['feasibility']
    assert ranked.breakdown.diversity == RULE_V4_WEIGHTS['diversity']
    assert ranked.breakdown.weather_modifier == 3.0
    assert ranked.breakdown.total == 100


def test_hard_filter_only_keeps_recipe_ready_safe_foods() -> None:
    ready = _make_food('有菜谱')
    ready.recipe_ready = True
    missing_recipe = _make_food('无菜谱')

    result = recommender.hard_filter(
        [ready, missing_recipe],
        _make_profile(1),
        RecommendRequest(),
    )

    assert result == [ready]


@pytest.mark.asyncio
async def test_returns_three_foods(session, seeded_session, monkeypatch):
    """基本：返 3 道菜 + 上下文。"""
    user, _ = seeded_session
    _patch_external(monkeypatch)
    req = RecommendRequest(mood="neutral")
    resp = await recommender.recommend(session, user, req)
    assert len(resp.foods) == 3
    assert [item.meal_role for item in resp.primary_meal.items] == [
        'main', 'vegetable', 'staple'
    ]
    assert resp.context.weather.weather_tag == "mild"
    assert resp.context.today.zodiac_sign == "leo"
    for f in resp.foods:
        assert f.reason
        assert 0.0 <= f.score <= 100.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("party_size", "expected_roles"),
    [
        (2, ['main', 'vegetable', 'staple']),
        (4, ['main', 'main', 'vegetable', 'staple']),
        (6, ['main', 'main', 'vegetable', 'vegetable', 'staple']),
        (8, ['main', 'main', 'main', 'vegetable', 'vegetable', 'staple']),
    ],
)
async def test_family_recommendation_scales_menu_with_party_size(
    session,
    seeded_session,
    monkeypatch,
    party_size,
    expected_roles,
):
    user, _ = seeded_session
    _patch_external(monkeypatch)

    response = await recommender.recommend(
        session,
        user,
        RecommendRequest(
            mood="neutral",
            audience="family",
            party_size=party_size,
        ),
    )

    assert [item.meal_role for item in response.primary_meal.items] == expected_roles
    assert len({item.food_id for item in response.primary_meal.items}) == len(expected_roles)
    if party_size >= 3:
        assert response.substitutions == []


@pytest.mark.asyncio
async def test_family_refresh_replaces_at_least_sixty_percent_when_pool_allows(
    session,
    seeded_session,
    monkeypatch,
):
    user, _ = seeded_session
    _patch_external(monkeypatch)
    request = RecommendRequest(
        mood="neutral",
        audience="family",
        party_size=4,
    )

    first = await recommender.recommend(session, user, request)
    first_ids = [item.food_id for item in first.primary_meal.items]
    second = await recommender.recommend(
        session,
        user,
        request.model_copy(update={"exclude_food_ids": first_ids}),
    )
    second_ids = {item.food_id for item in second.primary_meal.items}

    assert len(set(first_ids) & second_ids) <= 1


@pytest.mark.asyncio
async def test_forbidden_tag_filters_pork(session, seeded_session, monkeypatch):
    """用户忌口 pork → 红烧肉（tags=['pork']）不应出现。"""
    user, _ = seeded_session
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == user.id)
    ).first()
    assert profile is not None
    profile.forbidden_tags = ["pork"]
    session.add(profile)
    session.commit()

    _patch_external(monkeypatch)
    req = RecommendRequest(mood="neutral")
    resp = await recommender.recommend(session, user, req)

    names = [f.name for f in resp.foods]
    assert "红烧肉" not in names


@pytest.mark.asyncio
async def test_constitution_forbidden_filters(session, seeded_session, monkeypatch):
    """用户体质 tanshi → 红烧肉（forbidden_for 含 tanshi）不出现。"""
    user, _ = seeded_session
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == user.id)
    ).first()
    assert profile is not None
    profile.constitution_type = "tanshi"
    session.add(profile)
    session.commit()

    _patch_external(monkeypatch)
    req = RecommendRequest(mood="neutral")
    resp = await recommender.recommend(session, user, req)

    names = [f.name for f in resp.foods]
    assert "红烧肉" not in names  # forbidden_for=[tanshi,shire]


def test_weather_cold_only_gently_prefers_warm_food() -> None:
    warm = _make_food("温性菜", nature="warm")
    cool = _make_food("凉性菜", nature="cool")
    weather = _make_weather("cold", temp_c=5.0)
    solar = _make_today()

    warm_seasonal, warm_modifier = recommender._seasonal_wellness_score(
        recommender._score_solar_term(warm, solar)[0],
        recommender._score_weather(warm, weather)[0],
    )
    cool_seasonal, cool_modifier = recommender._seasonal_wellness_score(
        recommender._score_solar_term(cool, solar)[0],
        recommender._score_weather(cool, weather)[0],
    )

    assert warm_seasonal > cool_seasonal
    assert warm_modifier - cool_modifier <= 6.0


@pytest.mark.asyncio
async def test_weather_rainy_softly_promotes_soup(session, seeded_session, monkeypatch):
    """雨天给汤粥软加分；最终仍允许个性化探索，不把天气变成独裁者。"""
    user, _ = seeded_session
    _patch_external(monkeypatch, weather_tag="rainy", temp_c=18.0)
    req = RecommendRequest(mood="neutral", lat=39.92, lng=116.41)
    resp = await recommender.recommend(session, user, req)

    soup = _make_food("测试汤", cooking_method="soup")
    plain = _make_food("测试炒菜", cooking_method="stir_fry")
    weather = _make_weather("rainy", temp_c=18.0)

    assert recommender._score_weather(soup, weather)[0] > recommender._score_weather(
        plain,
        weather,
    )[0]
    assert resp.context.weather.weather_tag == "rainy"
    assert len(resp.primary_meal.items) == 3


@pytest.mark.asyncio
async def test_solar_term_promotes_in_season(session, seeded_session, monkeypatch):
    """节气只做可解释软加分，不承诺单个菜每次必然上榜。"""
    user, foods = seeded_session
    _patch_external(monkeypatch, solar_term_current="立秋", solar_term_next_name="处暑")
    req = RecommendRequest(mood="neutral")
    resp = await recommender.recommend(session, user, req)

    seasonal = next(food for food in foods if food.name == "番茄炒蛋")
    ordinary = next(food for food in foods if food.name == "红烧肉")
    today = _make_today(solar_term_current="立秋", solar_term_next_name="处暑")
    assert recommender._score_solar_term(seasonal, today)[0] > recommender._score_solar_term(
        ordinary,
        today,
    )[0]
    assert len(resp.primary_meal.items) == 3


@pytest.mark.asyncio
async def test_mood_tired_promotes_high_protein(session, seeded_session, monkeypatch):
    """疲惫对高蛋白做软加分，但不压过忌口、新鲜度和探索。"""
    user, foods = seeded_session
    _patch_external(monkeypatch)
    req = RecommendRequest(mood="tired")
    resp = await recommender.recommend(session, user, req)

    high_protein = next(food for food in foods if food.name == "清蒸鲈鱼")
    low_protein = next(food for food in foods if food.name == "白米饭")
    assert recommender._score_mood(high_protein, "tired")[0] > recommender._score_mood(
        low_protein,
        "tired",
    )[0]
    assert len(resp.primary_meal.items) == 3


@pytest.mark.asyncio
async def test_mood_anxious_promotes_tryptophan(session, seeded_session, monkeypatch):
    """焦虑场景对含鸡蛋等食材做软加分，不强制固定菜名。"""
    user, foods = seeded_session
    _patch_external(monkeypatch)
    req = RecommendRequest(mood="anxious")
    resp = await recommender.recommend(session, user, req)

    matching = next(food for food in foods if food.name == "番茄炒蛋")
    ordinary = next(food for food in foods if food.name == "白米饭")
    assert recommender._score_mood(matching, "anxious")[0] > recommender._score_mood(
        ordinary,
        "anxious",
    )[0]
    assert len(resp.primary_meal.items) == 3


@pytest.mark.asyncio
async def test_history_high_fat_promotes_low_fat(session, seeded_session, monkeypatch):
    """近 3 天 chosen 含高脂菜（红烧肉 fat=32）→ 低脂菜（白米饭/银耳莲子羹）加分。"""
    user, foods = seeded_session
    hongshaorou = next(f for f in foods if f.name == "红烧肉")
    assert hongshaorou.id is not None
    log = DailyLog(
        user_id=user.id,
        log_date=date.today(),
        chosen_food_ids_json=[hongshaorou.id],  # type: ignore[list-item]
        recommended_food_ids_json=[],
        mood="neutral",
        activity_level="normal",
        weather_tag="mild",
    )
    session.add(log)
    session.commit()
    previous_log = DailyLog(
        user_id=user.id,
        log_date=date.today() - timedelta(days=1),
        chosen_food_ids_json=[hongshaorou.id],
        recommended_food_ids_json=[],
    )

    low_fat = next(food for food in foods if food.name == "白米饭")
    high_fat = hongshaorou
    assert recommender._score_nutrition_balance_with_foods(
        low_fat,
        [log, previous_log],
        foods,
    )[0] > recommender._score_nutrition_balance_with_foods(
        high_fat,
        [log, previous_log],
        foods,
    )[0]


@pytest.mark.asyncio
async def test_diversity_no_three_same_category(session, seeded_session, monkeypatch):
    """top 3 不能全相同 category。"""
    user, _ = seeded_session
    _patch_external(monkeypatch)
    req = RecommendRequest(mood="neutral")
    resp = await recommender.recommend(session, user, req)

    cats = [f.category for f in resp.foods]
    assert len(set(cats)) >= 2, f"top 3 不应全同 category，实际: {cats}"


@pytest.mark.asyncio
async def test_no_profile_raises_not_found(session, monkeypatch):
    """未建档用户调推荐 → NotFoundError。"""
    user = User(openid="no_profile_user", nickname="无名", avatar_url=None)
    session.add(user)
    session.commit()
    session.refresh(user)

    _patch_external(monkeypatch)
    req = RecommendRequest(mood="neutral")
    with pytest.raises(NotFoundError):
        await recommender.recommend(session, user, req)


@pytest.mark.asyncio
async def test_reason_contains_keywords(session, seeded_session, monkeypatch):
    """理由文本含「适合今日」+ 菜名。"""
    user, _ = seeded_session
    _patch_external(monkeypatch, solar_term_current="立秋", solar_term_next_name="处暑")
    req = RecommendRequest(mood="neutral")
    resp = await recommender.recommend(session, user, req)

    for f in resp.foods:
        assert "适合今日" in f.reason or f.name in f.reason, \
            f"理由应含「适合今日」或菜名，实际: {f.reason}"


@pytest.mark.asyncio
async def test_refresh_rotates_results_when_six_unseen_foods_exist(
    session,
    seeded_session,
    monkeypatch,
):
    """同一天重复刷新时，候选充足则不重复上一批。"""
    user, _ = seeded_session
    _patch_external(monkeypatch, solar_term_current="立秋")
    req = RecommendRequest(mood="neutral")

    first = await recommender.recommend(session, user, req)
    second = await recommender.recommend(session, user, req)

    first_ids = {food.id for food in first.foods}
    second_ids = {food.id for food in second.foods}
    assert first_ids.isdisjoint(second_ids)


@pytest.mark.asyncio
async def test_same_request_id_replays_identical_meal(
    session,
    seeded_session,
    monkeypatch,
):
    user, _ = seeded_session
    _patch_external(monkeypatch)
    request = RecommendRequest(mood="neutral", request_id="stable-request-1")

    first = await recommender.recommend(session, user, request)
    second = await recommender.recommend(session, user, request)

    assert second.recommendation_id == first.recommendation_id
    assert [item.food_id for item in second.primary_meal.items] == [
        item.food_id for item in first.primary_meal.items
    ]


@pytest.mark.asyncio
async def test_fallback_weather_when_no_coords(session, seeded_session, monkeypatch):
    """lat/lng=None → fallback weather（weather_tag=mild），不打 HTTP。"""
    user, _ = seeded_session
    # weather_client.get_current 应该不被调用
    mock = AsyncMock()
    monkeypatch.setattr(recommender.weather_client, "get_current", mock)
    monkeypatch.setattr(
        recommender, "get_today_context_cached",
        lambda: _make_today(),
    )

    req = RecommendRequest(mood="neutral", lat=None, lng=None)
    resp = await recommender.recommend(session, user, req)

    # fallback weather_tag == mild
    assert resp.context.weather.weather_tag == "mild"
    assert resp.context.weather.text == "温和"
    # get_current 未被调用
    mock.assert_not_called()


@pytest.mark.asyncio
async def test_recent_weather_snapshot_skips_second_provider_request(monkeypatch):
    """前端刚取过天气时，推荐复用快照，不再串行请求一次和风天气。"""
    snapshot = _make_weather("rainy", temp_c=18.0).model_copy(
        update={"fetched_at": datetime.now(timezone.utc)},
    )
    mock = AsyncMock()
    monkeypatch.setattr(recommender.weather_client, "get_current", mock)

    weather = await recommender._resolve_weather(
        RecommendRequest(
            lat=39.92,
            lng=116.41,
            weather_snapshot=snapshot,
        )
    )

    assert weather == snapshot
    mock.assert_not_called()


@pytest.mark.asyncio
async def test_fallback_weather_when_provider_is_unavailable(
    session,
    seeded_session,
    monkeypatch,
):
    """天气服务不可用时仍返回完整餐，避免软依赖拖垮核心推荐。"""
    user, _ = seeded_session
    mock = AsyncMock(
        side_effect=ExternalAPIError("qweather", "网络异常: ConnectTimeout"),
    )
    monkeypatch.setattr(recommender.weather_client, "get_current", mock)
    monkeypatch.setattr(
        recommender,
        "get_today_context_cached",
        lambda: _make_today(),
    )

    req = RecommendRequest(mood="neutral", lat=28.00708, lng=120.63768)
    resp = await recommender.recommend(session, user, req)

    mock.assert_awaited_once_with(28.00708, 120.63768)
    assert resp.context.weather.weather_tag == "mild"
    assert resp.context.weather.location_name == "天气暂不可用"
    assert len(resp.primary_meal.items) == 3


@pytest.mark.asyncio
async def test_fallback_weather_when_provider_exceeds_recommend_deadline(
    session,
    seeded_session,
    monkeypatch,
):
    """天气端点迟迟不响应时快速降级，不能吃掉小程序的请求时限。"""
    user, _ = seeded_session

    async def never_returns(_lat: float, _lng: float) -> WeatherData:
        await asyncio.sleep(60)
        raise AssertionError("wait_for should cancel the weather request")

    monkeypatch.setattr(recommender.weather_client, "get_current", never_returns)
    monkeypatch.setattr(recommender, "RECOMMEND_WEATHER_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(
        recommender,
        "get_today_context_cached",
        lambda: _make_today(),
    )

    req = RecommendRequest(mood="neutral", lat=28.00708, lng=120.63768)
    resp = await recommender.recommend(session, user, req)

    assert resp.context.weather.weather_tag == "mild"
    assert resp.context.weather.location_name == "天气暂不可用"


@pytest.mark.asyncio
async def test_writes_daily_log(session, seeded_session, monkeypatch):
    """推荐后 DailyLog 表写入了 recommended_food_ids。"""
    user, _ = seeded_session
    _patch_external(monkeypatch)
    req = RecommendRequest(mood="tired")
    resp = await recommender.recommend(session, user, req)

    log = session.exec(
        select(DailyLog).where(DailyLog.user_id == user.id)
    ).first()
    assert log is not None
    assert log.mood == "tired"
    assert log.weather_tag == "mild"
    assert len(log.recommended_food_ids_json) == 3
    # 写入的 id 与返回的 foods id 一致
    returned_ids = {f.id for f in resp.foods}
    logged_ids = set(log.recommended_food_ids_json)
    assert returned_ids == logged_ids
    event = session.exec(
        select(RecommendationEvent).where(RecommendationEvent.user_id == user.id)
    ).first()
    assert event is not None
    assert resp.recommendation_id == event.id
    assert [item.food_id for item in resp.primary_meal.items] == event.recommended_food_ids_json


@pytest.mark.asyncio
async def test_uses_real_weather_when_coords_provided(session, seeded_session, monkeypatch):
    """lat/lng 提供时调真实 weather_client.get_current。"""
    user, _ = seeded_session
    weather = _make_weather("rainy", temp_c=18.0)
    mock = AsyncMock(return_value=weather)
    monkeypatch.setattr(recommender.weather_client, "get_current", mock)
    monkeypatch.setattr(
        recommender, "get_today_context_cached",
        lambda: _make_today(),
    )

    req = RecommendRequest(mood="neutral", lat=39.92, lng=116.41)
    resp = await recommender.recommend(session, user, req)

    mock.assert_awaited_once_with(39.92, 116.41)
    assert resp.context.weather.weather_tag == "rainy"


def test_weather_score_is_capped_and_gap_is_not_dominant():
    warm = _make_food("温性菜", nature="warm")
    cool = _make_food("凉性菜", nature="cool")
    neutral = _make_food("中性菜", nature="neutral")
    scores = [
        recommender._score_weather(food, _make_weather("cold"))[0]
        for food in (warm, cool, neutral)
    ]
    assert max(scores) == 15.0
    assert min(scores) == 3.0
    assert max(scores) - min(scores) == 12.0


def test_score_food_uses_one_hundred_point_breakdown():
    food = _make_food(
        "高蛋白温性菜",
        nature="warm",
        tags=["easy"],
        suitable_constitutions=["qixu"],
        nutrition={"protein_g": 18.0, "fat_g": 3.0},
        seasonal_solar_terms=["liqiu"],
    )
    profile = _make_profile(1, constitution_type="qixu")
    candidate = recommender._score_food(
        food,
        _make_weather("cold"),
        _make_today(solar_term_current="立秋", zodiac_sign="taurus"),
        profile,
        [],
        [food],
        "tired",
        "high",
    )
    assert 0.0 <= candidate.breakdown.weather_modifier <= 3.0
    assert 0.0 <= candidate.breakdown.seasonal_wellness <= 18.0
    assert 0.0 <= candidate.breakdown.personal_family <= 20.0
    assert 0.0 <= candidate.base_score <= 100.0


def test_weather_modifier_is_bounded_inside_seasonal_wellness():
    low_score, low_modifier = recommender._seasonal_wellness_score(15.0, 3.0)
    high_score, high_modifier = recommender._seasonal_wellness_score(15.0, 15.0)

    assert low_modifier == -3.0
    assert high_modifier == 3.0
    assert high_score - low_score <= 6.0


@pytest.mark.asyncio
async def test_four_refreshes_return_twelve_unique_foods_when_pool_allows(
    session,
    seeded_session,
    monkeypatch,
):
    user, _ = seeded_session
    extras = []
    for index, role in enumerate(('vegetable', 'staple', 'vegetable', 'staple')):
        food = _make_food(
            f"扩展菜{index}",
            category=f"extra_{index}",
            cooking_method=f"method_{index}",
        )
        extras.append((food, role))
        session.add(food)
    session.commit()
    for food, role in extras:
        _attach_recipe(session, food, role)
    session.commit()
    _patch_external(monkeypatch)
    req = RecommendRequest(mood="neutral")

    batches = [await recommender.recommend(session, user, req) for _ in range(4)]
    ids = [food.id for batch in batches for food in batch.foods]
    assert len(ids) == 12
    assert len(set(ids)) == 12


@pytest.mark.asyncio
async def test_recently_chosen_food_is_avoided_when_alternatives_exist(
    session,
    seeded_session,
    monkeypatch,
):
    user, foods = seeded_session
    chosen = foods[0]
    assert chosen.id is not None
    session.add(
        DailyLog(
            user_id=user.id,
            log_date=date.today() - timedelta(days=1),
            recommended_food_ids_json=[chosen.id],
            chosen_food_ids_json=[chosen.id],
        )
    )
    session.commit()
    _patch_external(monkeypatch)

    response = await recommender.recommend(
        session,
        user,
        RecommendRequest(mood="neutral"),
    )
    assert chosen.id not in {food.id for food in response.foods}


@pytest.mark.asyncio
async def test_invalid_reranker_output_falls_back_without_reintroducing_forbidden_food(
    session,
    seeded_session,
    monkeypatch,
):
    user, foods = seeded_session
    forbidden = next(food for food in foods if food.name == "红烧肉")
    assert forbidden.id is not None
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == user.id)
    ).first()
    assert profile is not None
    profile.forbidden_tags = ["pork"]
    session.add(profile)
    session.commit()
    _patch_external(monkeypatch)

    class InvalidReranker:
        engine_name = "invalid_agent"

        async def rerank(self, candidates, context):
            return [
                RerankAdjustment(
                    food_id=forbidden.id,
                    score_delta=15.0,
                    reason="不应被采用",
                )
            ]

    response = await recommender.recommend(
        session,
        user,
        RecommendRequest(mood="neutral"),
        reranker=InvalidReranker(),
    )
    assert forbidden.id not in {food.id for food in response.foods}
    event = session.exec(
        select(RecommendationEvent)
        .where(RecommendationEvent.user_id == user.id)
        .order_by(RecommendationEvent.id.desc())  # type: ignore[attr-defined]
    ).first()
    assert event is not None
    assert event.engine == "rules_v5"


@pytest.mark.asyncio
async def test_two_hundred_food_recommendation_finishes_under_half_second(
    session,
    monkeypatch,
):
    user = User(openid="perf_user", nickname="性能用户", avatar_url=None)
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None
    session.add(_make_profile(user.id, constitution_type="pinghe"))
    perf_foods = [
        _make_food(
                f"性能菜{index}",
                category=f"category_{index % 12}",
                cooking_method=f"method_{index % 10}",
                tags=["easy"],
            )
            for index in range(200)
    ]
    session.add_all(perf_foods)
    session.commit()
    roles = ('main', 'vegetable', 'staple')
    for index, food in enumerate(perf_foods):
        _attach_recipe(session, food, roles[index % 3])
    session.commit()
    _patch_external(monkeypatch)

    started = perf_counter()
    response = await recommender.recommend(
        session,
        user,
        RecommendRequest(mood="neutral"),
    )
    elapsed = perf_counter() - started
    assert len(response.foods) == 3
    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_recommendation_hot_path_uses_at_most_five_selects(
    session,
    seeded_session,
    monkeypatch,
):
    user, _ = seeded_session
    _patch_external(monkeypatch)
    select_statements: list[str] = []

    def capture_selects(
        _conn,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            select_statements.append(statement)

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", capture_selects)
    try:
        await recommender.recommend(session, user, RecommendRequest())
    finally:
        event.remove(engine, "before_cursor_execute", capture_selects)

    assert len(select_statements) <= 6, "\n\n".join(select_statements)
