from datetime import date, timedelta

import pytest

from app.models.daily_log import DailyLog
from app.models.recommendation_event import RecommendationEvent
from app.services.recommendation_ranking import (
    MAX_RULE_SCORE,
    RULE_V4_WEIGHTS,
    IdentityReranker,
    RankedCandidate,
    RecommendationHistory,
    RerankAdjustment,
    ScoreBreakdown,
    apply_novelty,
    apply_rerank_adjustments,
    build_recommendation_history,
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
            seasonal_wellness=0,
            personal_family=0,
            preference_history=0,
            feasibility=0,
            diversity=0,
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
