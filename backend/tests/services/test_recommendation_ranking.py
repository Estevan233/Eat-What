from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.daily_log import DailyLog
from app.models.favorite import Favorite
from app.models.food import Food
from app.models.recommendation_event import RecommendationEvent
from app.schemas.daily import MealIntent
from app.services.recommendation_ranking import (
    MAX_BASE_SCORE,
    MAX_RULE_SCORE,
    RULE_V4_WEIGHTS,
    RULE_V6_BASE_WEIGHTS,
    RULE_V6_RERANK_WEIGHTS,
    ExplicitPreferenceSignal,
    IdentityReranker,
    PreferenceSnapshot,
    RankedCandidate,
    RecommendationHistory,
    RerankAdjustment,
    ScoreBreakdown,
    apply_bounded_exploration,
    apply_novelty,
    apply_rerank_adjustments,
    build_preference_snapshot,
    build_recommendation_history,
    meal_intent_adjustment,
    preference_history_score,
    select_diverse,
    with_client_exclusions,
)
from tests.services.test_recommender import _make_food


def _candidate(food_id: int, *, score: float = 30.0) -> RankedCandidate:
    food = _make_food(f"菜{food_id}")
    food.id = food_id
    return RankedCandidate(
        food=food,
        base_score=score,
        breakdown=ScoreBreakdown(
            nutrition=0,
            constitution=0,
            solar_term=0,
            weather=0,
            preference=0,
            feasibility=0,
            mood=0,
            activity=0,
            zodiac=0,
        ),
        reason_phrases={},
    )


def test_rule_v4_weights_match_the_confirmed_product_model() -> None:
    assert RULE_V4_WEIGHTS == {
        "nutrition": 22,
        "seasonal_wellness": 18,
        "personal_family": 20,
        "preference_history": 15,
        "feasibility": 15,
        "diversity": 10,
    }
    assert sum(RULE_V4_WEIGHTS.values()) == 100
    assert MAX_RULE_SCORE == 100.0


def test_rule_v6_weights_split_eighty_five_base_and_fifteen_rerank() -> None:
    assert RULE_V6_BASE_WEIGHTS == {
        "nutrition": 12,
        "constitution": 14,
        "solar_term": 16,
        "weather": 4,
        "preference": 15,
        "feasibility": 14,
        "mood": 5,
        "activity": 3,
        "zodiac": 2,
    }
    assert RULE_V6_RERANK_WEIGHTS == {"diversity": 7, "exploration": 8}
    assert sum(RULE_V6_BASE_WEIGHTS.values()) == 85
    assert sum(RULE_V6_RERANK_WEIGHTS.values()) == 15
    assert MAX_BASE_SCORE == 85.0


def test_score_breakdown_total_is_capped_at_eighty_five() -> None:
    over = ScoreBreakdown(
        nutrition=12, constitution=14, solar_term=16, weather=4,
        preference=15, feasibility=14, mood=5, activity=3, zodiac=2,
    )
    assert over.total == 85.0
    assert over.total == MAX_BASE_SCORE


def test_meal_intent_soft_adjustment_is_bounded_and_explainable() -> None:
    matching = _make_food(
        "番茄鸡蛋",
        ingredients=["番茄", "鸡蛋"],
        nutrition={"protein_g": 18, "fat_g": 6, "carb_g": 8},
    )
    matching.cooking_time_min = 18
    intent = MealIntent(
        available_ingredients=["番茄", "鸡蛋"],
        max_time_minutes=20,
        goal="high_protein",
        summary="番茄鸡蛋，二十分钟，高蛋白",
    )

    delta, phrase = meal_intent_adjustment(matching, intent)

    assert 0 < delta <= 6
    assert "现有食材" in phrase


def test_meal_intent_time_overrun_is_only_a_bounded_soft_penalty() -> None:
    slow = _make_food("慢炖牛肉", ingredients=["牛肉"])
    slow.cooking_time_min = 90

    delta, _ = meal_intent_adjustment(
        slow,
        MealIntent(max_time_minutes=15, summary="十五分钟"),
    )

    assert -6 <= delta < 0


def test_normalized_score_is_clamped_to_zero_and_one_hundred():
    high = _candidate(1, score=MAX_RULE_SCORE + 20)
    low = _candidate(2, score=-20)
    assert high.normalized_score == 100.0
    assert low.normalized_score == 0.0


def test_rerank_adjustment_is_bounded_and_rejects_unknown_ids():
    candidates = [_candidate(1), _candidate(2)]
    adjusted = apply_rerank_adjustments(
        candidates,
        [RerankAdjustment(food_id=1, score_delta=999, reason="更符合口味")],
    )
    assert adjusted[0].rerank_adjustment == 10.0
    assert adjusted[0].rerank_reason == "更符合口味"

    try:
        apply_rerank_adjustments(
            candidates,
            [RerankAdjustment(food_id=999, score_delta=1)],
        )
    except ValueError as exc:
        assert "999" in str(exc)
    else:
        raise AssertionError("未知 food_id 必须被拒绝")


def test_duplicate_rerank_adjustments_are_rejected():
    candidates = [_candidate(1)]
    duplicate = [
        RerankAdjustment(food_id=1, score_delta=1),
        RerankAdjustment(food_id=1, score_delta=2),
    ]
    try:
        apply_rerank_adjustments(candidates, duplicate)
    except ValueError as exc:
        assert "重复" in str(exc)
    else:
        raise AssertionError("重复 food_id 必须被拒绝")


async def test_identity_reranker_returns_no_adjustments():
    reranker = IdentityReranker()
    assert reranker.engine_name == "rules_v4"
    assert await reranker.rerank([], None) == ()


def test_today_seen_foods_get_minus_forty_five_penalty():
    """rules_v6：当天曝光不再硬删除，而是 -45 惩罚压底，候选不足可回补。"""
    candidates = [_candidate(index, score=50 - index) for index in range(1, 7)]
    history = build_recommendation_history(
        [],
        [
            RecommendationEvent(
                user_id=1,
                event_date=date(2026, 8, 11),
                recommended_food_ids_json=[1, 2, 3],
            )
        ],
        as_of=date(2026, 8, 11),
    )
    result = apply_novelty(candidates, history, top_n=3)
    ids = [candidate.food.id for candidate in result]
    assert {1, 2, 3}.issubset(ids)
    for candidate in result:
        if candidate.food.id in {1, 2, 3}:
            assert candidate.novelty_penalty == -45.0
            assert candidate.exposure_distance_days == 0


def test_client_exclusions_extend_seen_without_mutating_other_history() -> None:
    history = RecommendationHistory(
        seen_today=frozenset({1}),
        chosen_days_ago={2: 1},
        exposed_days_ago={3: 2},
    )

    merged = with_client_exclusions(history, [4, 5, 5])

    assert merged.seen_today == frozenset({1, 4, 5})
    assert merged.chosen_days_ago == {2: 1}
    assert merged.exposed_days_ago == {3: 2}
    assert history.seen_today == frozenset({1})


def test_chosen_penalty_wins_over_exposure_penalty():
    today = date(2026, 8, 11)
    candidate = _candidate(1)
    history = build_recommendation_history(
        [
            DailyLog(
                user_id=1,
                log_date=today - timedelta(days=1),
                recommended_food_ids_json=[1],
                chosen_food_ids_json=[1],
            )
        ],
        [
            RecommendationEvent(
                user_id=1,
                event_date=today - timedelta(days=1),
                recommended_food_ids_json=[1],
            )
        ],
        as_of=today,
    )
    result = apply_novelty([candidate], history, top_n=3)
    # chosen(1)=-32 强于 exposed(1)=-16，只取最强不叠加
    assert result[0].novelty_penalty == -32.0


def test_seen_foods_return_with_penalty_when_pool_is_too_small():
    today = date(2026, 8, 11)
    history = build_recommendation_history(
        [],
        [
            RecommendationEvent(
                user_id=1,
                event_date=today,
                recommended_food_ids_json=[1, 2],
            )
        ],
        as_of=today,
    )
    result = apply_novelty([_candidate(1), _candidate(2)], history, top_n=3)
    assert len(result) == 2
    assert all(candidate.novelty_penalty == -45.0 for candidate in result)


@pytest.mark.parametrize("days_ago", range(1, 14))
def test_chosen_penalty_is_stronger_than_exposure_and_monotonic(days_ago: int) -> None:
    """rules_v6：1..13 天 chosen 公式衰减且始终强于同日 exposed。"""
    today = date(2026, 8, 11)
    chosen_history = build_recommendation_history(
        [DailyLog(user_id=1, log_date=today - timedelta(days=days_ago), chosen_food_ids_json=[1])],
        [],
        as_of=today,
    )
    exposed_history = build_recommendation_history(
        [],
        [RecommendationEvent(user_id=1, event_date=today - timedelta(days=days_ago), recommended_food_ids_json=[1])],
        as_of=today,
    )
    chosen_pen = apply_novelty([_candidate(1)], chosen_history, top_n=3)[0].novelty_penalty
    exposed_pen = apply_novelty([_candidate(1)], exposed_history, top_n=3)[0].novelty_penalty
    assert chosen_pen == -round(32.0 * (14 - days_ago) / 13.0, 2)
    assert exposed_pen == -round(16.0 * (14 - days_ago) / 13.0, 2)
    assert chosen_pen <= exposed_pen


def test_day_fourteen_has_no_novelty_penalty() -> None:
    today = date(2026, 8, 11)
    history = build_recommendation_history(
        [DailyLog(user_id=1, log_date=today - timedelta(days=14), chosen_food_ids_json=[1])],
        [RecommendationEvent(user_id=1, event_date=today - timedelta(days=14), recommended_food_ids_json=[1])],
        as_of=today,
    )
    result = apply_novelty([_candidate(1)], history, top_n=3)
    assert result[0].novelty_penalty == 0.0


def test_novelty_uses_strongest_signal_without_stacking() -> None:
    """当天曝光(-45) + 第1天选择(-32) + 第1天曝光(-16)：只取最强 -45。"""
    today = date(2026, 8, 11)
    history = build_recommendation_history(
        [DailyLog(user_id=1, log_date=today - timedelta(days=1), chosen_food_ids_json=[1])],
        [
            RecommendationEvent(user_id=1, event_date=today, recommended_food_ids_json=[1]),
            RecommendationEvent(user_id=1, event_date=today - timedelta(days=1), recommended_food_ids_json=[1]),
        ],
        as_of=today,
    )
    result = apply_novelty([_candidate(1)], history, top_n=3)
    assert result[0].novelty_penalty == -45.0


def test_unexposed_distance_is_thirty_day_sentinel() -> None:
    today = date(2026, 8, 11)
    history = build_recommendation_history([], [], as_of=today)
    result = apply_novelty([_candidate(1), _candidate(2)], history, top_n=3)
    assert all(candidate.exposure_distance_days == 30 for candidate in result)
    assert all(candidate.novelty_penalty == 0.0 for candidate in result)


def test_repeated_exposure_adds_a_bounded_freshness_penalty() -> None:
    today = date(2026, 8, 11)
    once = build_recommendation_history(
        [],
        [
            RecommendationEvent(
                user_id=1,
                event_date=today - timedelta(days=2),
                recommended_food_ids_json=[1],
            )
        ],
        as_of=today,
    )
    repeated = build_recommendation_history(
        [],
        [
            RecommendationEvent(
                user_id=1,
                event_date=today - timedelta(days=2),
                recommended_food_ids_json=[1],
            ),
            RecommendationEvent(
                user_id=1,
                event_date=today - timedelta(days=4),
                recommended_food_ids_json=[1],
            ),
        ],
        as_of=today,
    )

    once_ranked = apply_novelty([_candidate(1)], once, top_n=3)[0]
    repeated_ranked = apply_novelty([_candidate(1)], repeated, top_n=3)[0]

    assert repeated.exposure_counts[1] == 2
    assert repeated_ranked.novelty_penalty < once_ranked.novelty_penalty


def test_select_diverse_prefers_distinct_category_and_method():
    candidates = []
    specs = [
        (1, "soup", "soup", 60),
        (2, "soup", "soup", 59),
        (3, "staple", "boil", 58),
        (4, "steam", "steam", 57),
    ]
    for food_id, category, method, score in specs:
        candidate = _candidate(food_id, score=score)
        candidate.food.category = category
        candidate.food.cooking_method = method
        candidates.append(candidate)
    result = select_diverse(candidates, top_n=3)
    assert [candidate.food.id for candidate in result] == [1, 3, 4]


def test_select_diverse_relaxes_constraints_when_pool_is_small():
    candidates = [_candidate(1), _candidate(2)]
    for candidate in candidates:
        candidate.food.category = "soup"
        candidate.food.cooking_method = "soup"
    result = select_diverse(candidates, top_n=3)
    assert [candidate.food.id for candidate in result] == [1, 2]


def test_history_can_exclude_the_same_idempotency_request() -> None:
    today = date(2026, 8, 11)
    history = build_recommendation_history(
        [],
        [
            RecommendationEvent(
                request_id="same-request",
                user_id=1,
                event_date=today,
                recommended_food_ids_json=[1, 2, 3],
            ),
            RecommendationEvent(
                request_id="previous-request",
                user_id=1,
                event_date=today,
                recommended_food_ids_json=[4],
            ),
        ],
        as_of=today,
        exclude_request_id="same-request",
    )

    assert history.seen_today == frozenset({4})


def test_preference_snapshot_boosts_similar_food_without_unbounded_repeat() -> None:
    favorite = _candidate(1).food
    favorite.category = "soup"
    favorite.cooking_method = "stew"
    favorite.ingredients_json = ["番茄", "牛肉"]
    similar = _candidate(2).food
    similar.category = "soup"
    similar.cooking_method = "stew"
    similar.ingredients_json = ["番茄", "鸡蛋"]
    unrelated = _candidate(3).food
    unrelated.category = "cold_dish"
    unrelated.cooking_method = "cold"
    unrelated.ingredients_json = ["黄瓜"]

    snapshot = build_preference_snapshot(
        [favorite, similar, unrelated],
        [],
        [Favorite(user_id=1, food_id=1, created_at=datetime.now(timezone.utc))],
        [],
        as_of=date.today(),
    )

    assert isinstance(snapshot, PreferenceSnapshot)
    assert preference_history_score(similar, snapshot) > preference_history_score(
        unrelated, snapshot
    )
    assert 0 <= preference_history_score(favorite, snapshot) <= 15


def test_bounded_exploration_is_stable_and_never_leaves_quality_band_first() -> None:
    candidates = [_candidate(1, score=100), _candidate(2, score=97), _candidate(3, score=94)]

    first = apply_bounded_exploration(
        candidates,
        user_id=7,
        event_date=date(2026, 8, 11),
        request_id="request-a",
        meal_role="main",
    )
    repeated = apply_bounded_exploration(
        candidates,
        user_id=7,
        event_date=date(2026, 8, 11),
        request_id="request-a",
        meal_role="main",
    )

    assert [item.food.id for item in first] == [item.food.id for item in repeated]
    assert {item.food.id for item in first[:2]} == {1, 2}
    assert first[-1].food.id == 3


def test_bounded_exploration_varies_by_user_inside_same_quality_band() -> None:
    candidates = [_candidate(food_id, score=100) for food_id in range(1, 9)]

    first = apply_bounded_exploration(
        candidates,
        user_id=101,
        event_date=date(2026, 8, 11),
        request_id="same-request",
        meal_role="main",
    )
    second = apply_bounded_exploration(
        candidates,
        user_id=202,
        event_date=date(2026, 8, 11),
        request_id="same-request",
        meal_role="main",
    )

    assert [item.food.id for item in first] != [item.food.id for item in second]


# ---- rules_v6 30 天偏好画像 ----

_AS_OF = date(2026, 8, 29)


def _pref_food(food_id: int, name: str = "菜", **kwargs) -> Food:
    food = _make_food(name, **kwargs)
    food.id = food_id
    return food


def test_empty_preference_snapshot_returns_neutral_seven_point_five() -> None:
    snap = build_preference_snapshot([], [], [], [], as_of=_AS_OF)
    assert preference_history_score(_pref_food(1), snap) == 7.5


def test_preference_snapshot_contains_tag_category_nature_method_and_ingredient() -> None:
    food = _pref_food(
        1, "番茄炖牛", category="stew", cooking_method="stew", nature="warm",
        tags=["soup", "nourish"], ingredients=["番茄", "牛肉"],
    )
    fav = Favorite(user_id=1, food_id=1, created_at=datetime.now(timezone.utc))
    snap = build_preference_snapshot([food], [], [fav], [], as_of=_AS_OF)
    assert snap.category_affinity
    assert snap.method_affinity
    assert snap.nature_affinity
    assert snap.tag_affinity
    assert snap.ingredient_affinity


def test_favorite_signal_outweighs_chosen_signal() -> None:
    food = _pref_food(1, category="soup")
    fav = Favorite(user_id=1, food_id=1, created_at=datetime.now(timezone.utc))
    log = DailyLog(user_id=1, log_date=_AS_OF, chosen_food_ids_json=[1])
    snap_fav = build_preference_snapshot([food], [], [fav], [], as_of=_AS_OF)
    snap_chosen = build_preference_snapshot([food], [log], [], [], as_of=_AS_OF)
    assert snap_fav.category_affinity["soup"] > snap_chosen.category_affinity.get("soup", 0.0)


def test_chosen_signal_decays_by_recency_bucket() -> None:
    food = _pref_food(1, category="soup")
    recent = DailyLog(user_id=1, log_date=_AS_OF, chosen_food_ids_json=[1])        # decay 1.0
    older = DailyLog(user_id=1, log_date=date(2026, 8, 15), chosen_food_ids_json=[1])  # decay 0.6
    snap_recent = build_preference_snapshot([food], [recent], [], [], as_of=_AS_OF)
    snap_older = build_preference_snapshot([food], [older], [], [], as_of=_AS_OF)
    assert snap_recent.category_affinity["soup"] > snap_older.category_affinity.get("soup", 0.0)


def test_chosen_signal_is_damped_by_exposure_count() -> None:
    food = _pref_food(1, category="soup")
    log = DailyLog(user_id=1, log_date=_AS_OF, chosen_food_ids_json=[1])
    once = build_preference_snapshot([food], [log], [], [], as_of=_AS_OF)
    events = [
        RecommendationEvent(user_id=1, event_date=date(2026, 8, 28), recommended_food_ids_json=[1])
        for _ in range(4)
    ]
    many = build_preference_snapshot([food], [log], [], events, as_of=_AS_OF)
    assert once.category_affinity["soup"] >= many.category_affinity.get("soup", 0.0)


def test_exposed_but_not_chosen_is_not_negative_feedback() -> None:
    food = _pref_food(1, category="soup")
    events = [RecommendationEvent(user_id=1, event_date=date(2026, 8, 28), recommended_food_ids_json=[1])]
    snap = build_preference_snapshot([food], [], [], events, as_of=_AS_OF)
    assert preference_history_score(food, snap) == 7.5
    assert not snap.negative_category


def test_explicit_negative_signal_requires_explicit_input() -> None:
    food = _pref_food(
        1, category="soup", cooking_method="stew", nature="warm", tags=["t1"], ingredients=["番茄"],
    )
    neg = ExplicitPreferenceSignal(food_id=1, action="not_interested", occurred_on=date(2026, 8, 28))
    snap_no_neg = build_preference_snapshot([food], [], [], [], as_of=_AS_OF)
    snap_neg = build_preference_snapshot([food], [], [], [], as_of=_AS_OF, negative_signals=[neg])
    assert preference_history_score(food, snap_neg) < preference_history_score(food, snap_no_neg)


def test_preference_snapshot_uses_only_last_thirty_days() -> None:
    food = _pref_food(1, category="soup")
    old_fav = Favorite(user_id=1, food_id=1, created_at=datetime(2026, 7, 29, tzinfo=timezone.utc))
    snap = build_preference_snapshot([food], [], [old_fav], [], as_of=_AS_OF)
    assert preference_history_score(food, snap) == 7.5


# ---- rules_v6 质量带探索 ----

def test_unexposed_candidate_inside_quality_band_gets_eight() -> None:
    high = replace(_candidate(1, score=100), exposure_distance_days=1)   # band峰且已曝光
    unexposed = _candidate(2, score=96)                                  # band内未曝光
    result = apply_bounded_exploration(
        [high, unexposed], user_id=1, event_date=date(2026, 8, 11), request_id='r', meal_role='main',
    )
    by_id = {c.food.id: c for c in result}
    assert by_id[2].exploration_bonus == 8.0
    assert by_id[1].exploration_bonus == 0.0


def test_unexposed_candidate_outside_quality_band_gets_no_exploration_bonus() -> None:
    high = _candidate(1, score=100)
    unexposed_far = _candidate(2, score=90)  # 100-90=10 > 5，band 外
    result = apply_bounded_exploration(
        [high, unexposed_far], user_id=1, event_date=date(2026, 8, 11), request_id='r', meal_role='main',
    )
    by_id = {c.food.id: c for c in result}
    assert by_id[2].exploration_bonus == 0.0


def test_request_seed_does_not_change_quality_band_membership() -> None:
    candidates = [_candidate(1, score=100), _candidate(2, score=96)]
    a = apply_bounded_exploration(
        candidates, user_id=1, event_date=date(2026, 8, 11), request_id='r1', meal_role='main',
    )
    b = apply_bounded_exploration(
        candidates, user_id=1, event_date=date(2026, 8, 11), request_id='r2', meal_role='main',
    )
    assert {c.exploration_bonus for c in a} == {c.exploration_bonus for c in b}


def test_no_unexposed_in_band_does_not_expand_quality_band() -> None:
    high = replace(_candidate(1, score=100), exposure_distance_days=1)
    low = replace(_candidate(2, score=96), exposure_distance_days=1)  # 已曝光
    result = apply_bounded_exploration(
        [high, low], user_id=1, event_date=date(2026, 8, 11), request_id='r', meal_role='main',
    )
    assert all(c.exploration_bonus == 0.0 for c in result)
