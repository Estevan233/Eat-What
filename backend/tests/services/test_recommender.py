"""T10 推荐算法核心 service 单测。

覆盖 PRD 算法主要分支：
1. 基本：返 3 道菜 + 上下文
2. 硬筛：忌口（forbidden_tags）剔除
3. 硬筛：体质禁忌（forbidden_for）剔除
4. 天气 cold + 温热性菜 → 上榜
5. 天气 rainy + 汤粥类 → 上榜
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
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlmodel import select

from app.core.errors import NotFoundError
from app.models.daily_log import DailyLog
from app.models.food import Food
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.daily import RecommendRequest
from app.schemas.today_context import TodayContext
from app.schemas.weather import WeatherData
from app.services import recommender

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
    return user, foods


# ---- 测试 ----


@pytest.mark.asyncio
async def test_returns_three_foods(session, seeded_session, monkeypatch):
    """基本：返 3 道菜 + 上下文。"""
    user, _ = seeded_session
    _patch_external(monkeypatch)
    req = RecommendRequest(mood="neutral")
    resp = await recommender.recommend(session, user, req)
    assert len(resp.foods) == 3
    assert resp.context.weather.weather_tag == "mild"
    assert resp.context.today.zodiac_sign == "leo"
    for f in resp.foods:
        assert f.reason
        assert 0.0 <= f.score <= 100.0


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


@pytest.mark.asyncio
async def test_weather_cold_promotes_warm(session, seeded_session, monkeypatch):
    """天气 cold + 温热性菜（清炖牛肉/羊肉汤 nature=warm）→ 上榜。"""
    user, _ = seeded_session
    _patch_external(monkeypatch, weather_tag="cold", temp_c=5.0)
    # 提供坐标才会走 weather_client，从而命中 cold tag
    req = RecommendRequest(mood="neutral", lat=39.92, lng=116.41)
    resp = await recommender.recommend(session, user, req)

    names = [f.name for f in resp.foods]
    warm_foods = {"清炖牛肉", "羊肉汤"}  # nature=warm
    assert bool(set(names) & warm_foods), f"温热性菜应上榜，实际: {names}"


@pytest.mark.asyncio
async def test_weather_rainy_promotes_soup(session, seeded_session, monkeypatch):
    """天气 rainy + 汤粥类（cooking_method in soup/congee）→ 上榜。"""
    user, _ = seeded_session
    _patch_external(monkeypatch, weather_tag="rainy", temp_c=18.0)
    req = RecommendRequest(mood="neutral", lat=39.92, lng=116.41)
    resp = await recommender.recommend(session, user, req)

    names = [f.name for f in resp.foods]
    soup_foods = {"小米粥", "银耳莲子羹", "羊肉汤"}  # cooking_method soup/congee
    assert bool(set(names) & soup_foods), f"汤粥类应上榜，实际: {names}"


@pytest.mark.asyncio
async def test_solar_term_promotes_in_season(session, seeded_session, monkeypatch):
    """节气立秋当天 + 番茄炒蛋（seasonal_solar_terms=['liqiu']）→ 上榜。"""
    user, _ = seeded_session
    _patch_external(monkeypatch, solar_term_current="立秋", solar_term_next_name="处暑")
    req = RecommendRequest(mood="neutral")
    resp = await recommender.recommend(session, user, req)

    names = [f.name for f in resp.foods]
    assert "番茄炒蛋" in names, f"立秋时令菜应上榜，实际: {names}"


@pytest.mark.asyncio
async def test_mood_tired_promotes_high_protein(session, seeded_session, monkeypatch):
    """心情 tired + 高蛋白菜（清蒸鲈鱼 protein=18.6）→ 上榜。"""
    user, _ = seeded_session
    _patch_external(monkeypatch)
    req = RecommendRequest(mood="tired")
    resp = await recommender.recommend(session, user, req)

    names = [f.name for f in resp.foods]
    high_protein = {"清蒸鲈鱼", "清炖牛肉", "羊肉汤"}  # protein_g >= 8
    assert bool(set(names) & high_protein), f"高蛋白菜应上榜，实际: {names}"


@pytest.mark.asyncio
async def test_mood_anxious_promotes_tryptophan(session, seeded_session, monkeypatch):
    """心情 anxious + 含色氨酸食材（番茄炒蛋含「鸡蛋」）→ 上榜。"""
    user, _ = seeded_session
    _patch_external(monkeypatch)
    req = RecommendRequest(mood="anxious")
    resp = await recommender.recommend(session, user, req)

    names = [f.name for f in resp.foods]
    assert "番茄炒蛋" in names, f"含色氨酸食材的菜应上榜，实际: {names}"


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

    _patch_external(monkeypatch)
    req = RecommendRequest(mood="neutral")
    resp = await recommender.recommend(session, user, req)

    names = [f.name for f in resp.foods]
    low_fat = {"白米饭", "银耳莲子羹", "小米粥"}  # fat_g <= 5
    assert bool(set(names) & low_fat), f"低脂互补菜应上榜，实际: {names}"


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
async def test_stable_result_for_same_input(session, seeded_session, monkeypatch):
    """同输入两次推荐结果一致（不含随机/时间敏感性）。"""
    user, _ = seeded_session
    _patch_external(monkeypatch, solar_term_current="立秋")

    req = RecommendRequest(mood="neutral")
    resp1 = await recommender.recommend(session, user, req)
    resp2 = await recommender.recommend(session, user, req)

    names1 = [f.name for f in resp1.foods]
    names2 = [f.name for f in resp2.foods]
    assert names1 == names2, f"同输入结果应稳定，实际: {names1} vs {names2}"


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
