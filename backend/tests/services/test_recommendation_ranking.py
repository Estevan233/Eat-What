from datetime import date, timedelta

import pytest

from app.models.daily_log import DailyLog
from app.models.recommendation_event import RecommendationEvent
from app.services.recommendation_ranking import (
    MAX_RULE_SCORE,
    RULE_V3_WEIGHTS,
    IdentityReranker,
    RankedCandidate,
    RerankAdjustment,
    ScoreBreakdown,
    apply_novelty,
    apply_rerank_adjustments,
    build_recommendation_history,
    select_diverse,
)
from tests.services.test_recommender import _make_food


def _candidate(food_id: int, *, score: float = 30.0) -> RankedCandidate:
    food = _make_food(f"菜{food_id}")
    food.id = food_id
    return RankedCandidate(
        food=food,
        base_score=score,
        breakdown=ScoreBreakdown(
            weather=0,
            solar_term=0,
            mood=0,
            nutrition=0,
            constitution=0,
            activity=0,
            zodiac=0,
        ),
        reason_phrases={},
    )


def test_rule_v3_weights_make_weather_a_minor_signal() -> None:
    assert RULE_V3_WEIGHTS == {
        "nutrition": 20,
        "constitution": 12,
        "mood": 10,
        "activity": 8,
        "method_time": 13,
        "weather": 6,
        "solar_term": 5,
        "zodiac": 1,
    }
    assert sum(RULE_V3_WEIGHTS.values()) == 75
    assert RULE_V3_WEIGHTS["weather"] < RULE_V3_WEIGHTS["nutrition"]


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
    assert reranker.engine_name == "rules_v3"
    assert await reranker.rerank([], None) == ()


def test_today_seen_foods_are_excluded_when_three_unseen_exist():
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
    assert [candidate.food.id for candidate in result] == [4, 5, 6]


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
    assert result[0].novelty_penalty == -24.0


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
    assert all(candidate.novelty_penalty == -30.0 for candidate in result)


@pytest.mark.parametrize(
    ("days_ago", "expected"),
    list(enumerate([-30.0, -24.0, -18.0, -12.0, -8.0, -5.0, -3.0])),
)
def test_chosen_penalty_decays_across_seven_days(days_ago, expected):
    today = date(2026, 8, 11)
    history = build_recommendation_history(
        [
            DailyLog(
                user_id=1,
                log_date=today - timedelta(days=days_ago),
                chosen_food_ids_json=[1],
            )
        ],
        [],
        as_of=today,
    )
    result = apply_novelty([_candidate(1)], history, top_n=3)
    assert result[0].novelty_penalty == expected


@pytest.mark.parametrize(
    ("days_ago", "expected"),
    [
        (0, -30.0),
        (1, -10.0),
        (2, -8.0),
        (3, -6.0),
        (4, -4.0),
        (5, -3.0),
        (6, -2.0),
    ],
)
def test_exposure_penalty_decays_across_seven_days(days_ago, expected):
    today = date(2026, 8, 11)
    history = build_recommendation_history(
        [],
        [
            RecommendationEvent(
                user_id=1,
                event_date=today - timedelta(days=days_ago),
                recommended_food_ids_json=[1],
            )
        ],
        as_of=today,
    )
    result = apply_novelty([_candidate(1)], history, top_n=3)
    assert result[0].novelty_penalty == expected


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
