"""推荐排序领域类型与纯函数。"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Protocol

from app.models.daily_log import DailyLog
from app.models.food import Food
from app.models.recommendation_event import RecommendationEvent

RULE_V3_WEIGHTS = {
    "nutrition": 20,
    "constitution": 12,
    "mood": 10,
    "activity": 8,
    "method_time": 13,
    "weather": 6,
    "solar_term": 5,
    "zodiac": 1,
}
MAX_RULE_SCORE = 75.0
MAX_RERANK_DELTA = 10.0
CHOSEN_PENALTIES = (-30.0, -24.0, -18.0, -12.0, -8.0, -5.0, -3.0)
EXPOSED_PENALTIES = (-12.0, -10.0, -8.0, -6.0, -4.0, -3.0, -2.0)
SEEN_TODAY_PENALTY = -30.0


@dataclass(frozen=True)
class ScoreBreakdown:
    weather: float
    solar_term: float
    mood: float
    nutrition: float
    constitution: float
    activity: float
    zodiac: float
    method_time: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.weather
            + self.solar_term
            + self.mood
            + self.nutrition
            + self.constitution
            + self.activity
            + self.method_time
            + self.zodiac
        )


@dataclass(frozen=True)
class RankedCandidate:
    food: Food
    base_score: float
    breakdown: ScoreBreakdown
    reason_phrases: Mapping[str, str]
    rerank_adjustment: float = 0.0
    novelty_penalty: float = 0.0
    rerank_reason: str | None = None

    @property
    def final_raw_score(self) -> float:
        return self.base_score + self.rerank_adjustment + self.novelty_penalty

    @property
    def normalized_score(self) -> float:
        bounded = max(0.0, min(MAX_RULE_SCORE, self.final_raw_score))
        return round(bounded / MAX_RULE_SCORE * 100.0, 2)


@dataclass(frozen=True)
class RecommendationRankingContext:
    mood: str
    activity_level: str
    weather_tag: str
    solar_term: str
    constitution_types: tuple[str, ...]


@dataclass(frozen=True)
class RecommendationHistory:
    seen_today: frozenset[int]
    chosen_days_ago: Mapping[int, int]
    exposed_days_ago: Mapping[int, int]


@dataclass(frozen=True)
class RerankAdjustment:
    food_id: int
    score_delta: float
    reason: str | None = None


class CandidateReranker(Protocol):
    engine_name: str

    async def rerank(
        self,
        candidates: Sequence[RankedCandidate],
        context: RecommendationRankingContext | None,
    ) -> Sequence[RerankAdjustment]: ...


class IdentityReranker:
    engine_name = "rules_v3"

    async def rerank(
        self,
        candidates: Sequence[RankedCandidate],
        context: RecommendationRankingContext | None,
    ) -> Sequence[RerankAdjustment]:
        return ()


def apply_rerank_adjustments(
    candidates: Sequence[RankedCandidate],
    adjustments: Sequence[RerankAdjustment],
) -> list[RankedCandidate]:
    """校验重排输出并把分数调整限制在安全区间。"""
    candidate_ids = {candidate.food.id for candidate in candidates}
    by_id: dict[int, RerankAdjustment] = {}
    for proposed_adjustment in adjustments:
        if proposed_adjustment.food_id not in candidate_ids:
            raise ValueError(
                f"重排结果包含未知 food_id={proposed_adjustment.food_id}"
            )
        if proposed_adjustment.food_id in by_id:
            raise ValueError(
                f"重排结果包含重复 food_id={proposed_adjustment.food_id}"
            )
        by_id[proposed_adjustment.food_id] = proposed_adjustment

    result: list[RankedCandidate] = []
    for candidate in candidates:
        food_id = candidate.food.id
        adjustment = by_id.get(food_id) if food_id is not None else None
        if adjustment is None:
            result.append(candidate)
            continue
        delta = max(-MAX_RERANK_DELTA, min(MAX_RERANK_DELTA, adjustment.score_delta))
        result.append(
            replace(
                candidate,
                rerank_adjustment=delta,
                rerank_reason=adjustment.reason,
            )
        )
    return result


def _remember_nearest(target: dict[int, int], food_id: int, days_ago: int) -> None:
    previous = target.get(food_id)
    if previous is None or days_ago < previous:
        target[food_id] = days_ago


def build_recommendation_history(
    logs: Sequence[DailyLog],
    events: Sequence[RecommendationEvent],
    *,
    as_of: date,
) -> RecommendationHistory:
    """把七天日志压缩成每道菜距今最近的选择与曝光天数。"""
    chosen: dict[int, int] = {}
    exposed: dict[int, int] = {}
    seen_today: set[int] = set()
    for log_record in logs:
        days_ago = (as_of - log_record.log_date).days
        if 0 <= days_ago < len(CHOSEN_PENALTIES):
            for food_id in log_record.chosen_food_ids_json or []:
                _remember_nearest(chosen, food_id, days_ago)
    for event in events:
        days_ago = (as_of - event.event_date).days
        if not 0 <= days_ago < len(EXPOSED_PENALTIES):
            continue
        for food_id in event.recommended_food_ids_json or []:
            _remember_nearest(exposed, food_id, days_ago)
            if days_ago == 0:
                seen_today.add(food_id)
    return RecommendationHistory(
        seen_today=frozenset(seen_today),
        chosen_days_ago=chosen,
        exposed_days_ago=exposed,
    )


def apply_novelty(
    candidates: Sequence[RankedCandidate],
    history: RecommendationHistory,
    *,
    top_n: int,
) -> list[RankedCandidate]:
    """优先排除当天已展示菜，并按七天历史应用非叠加惩罚。"""
    unseen_count = sum(
        candidate.food.id not in history.seen_today
        for candidate in candidates
    )
    exclude_seen = unseen_count >= top_n
    result: list[RankedCandidate] = []
    for candidate in candidates:
        food_id = candidate.food.id
        if food_id is None:
            continue
        if exclude_seen and food_id in history.seen_today:
            continue
        penalties: list[float] = []
        chosen_days = history.chosen_days_ago.get(food_id)
        if chosen_days is not None:
            penalties.append(CHOSEN_PENALTIES[chosen_days])
        else:
            exposed_days = history.exposed_days_ago.get(food_id)
            if exposed_days is not None:
                penalties.append(EXPOSED_PENALTIES[exposed_days])
        if food_id in history.seen_today:
            penalties.append(SEEN_TODAY_PENALTY)
        penalty = min(penalties, default=0.0)
        result.append(replace(candidate, novelty_penalty=penalty))
    return result


def _append_diverse_pass(
    ordered: Sequence[RankedCandidate],
    selected: list[RankedCandidate],
    selected_ids: set[int],
    categories: set[str],
    methods: set[str],
    *,
    top_n: int,
    require_new_category: bool,
    require_new_method: bool,
) -> None:
    """执行一轮约束选择，并原地更新已选集合。"""
    for candidate in ordered:
        if len(selected) >= top_n:
            return
        food_id = candidate.food.id
        if food_id is None or food_id in selected_ids:
            continue
        if require_new_category and candidate.food.category in categories:
            continue
        if require_new_method and candidate.food.cooking_method in methods:
            continue
        selected.append(candidate)
        selected_ids.add(food_id)
        categories.add(candidate.food.category)
        methods.add(candidate.food.cooking_method)


def select_diverse(
    candidates: Sequence[RankedCandidate],
    *,
    top_n: int,
) -> list[RankedCandidate]:
    """在完整候选池中分三阶段选择，优先保证品类和做法不同。"""
    ordered = sorted(
        candidates,
        key=lambda candidate: (
            -candidate.final_raw_score,
            candidate.food.id or 0,
        ),
    )
    selected: list[RankedCandidate] = []
    selected_ids: set[int] = set()
    categories: set[str] = set()
    methods: set[str] = set()
    for require_new_category, require_new_method in (
        (True, True),
        (True, False),
        (False, False),
    ):
        _append_diverse_pass(
            ordered,
            selected,
            selected_ids,
            categories,
            methods,
            top_n=top_n,
            require_new_category=require_new_category,
            require_new_method=require_new_method,
        )

    return selected
