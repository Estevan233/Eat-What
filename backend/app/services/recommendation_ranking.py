"""推荐排序领域类型与纯函数。"""
import hashlib
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Protocol

from app.models.daily_log import DailyLog
from app.models.food import Food
from app.models.recommendation_event import RecommendationEvent
from app.schemas.daily import MealIntent

RULE_V4_WEIGHTS = {
    "nutrition": 22,
    "seasonal_wellness": 18,
    "personal_family": 20,
    "preference_history": 15,
    "feasibility": 15,
    "diversity": 10,
}
MAX_RULE_SCORE = 100.0
MAX_RERANK_DELTA = 10.0
MAX_MEAL_INTENT_DELTA = 6.0
CHOSEN_PENALTIES = (-30.0, -24.0, -18.0, -12.0, -8.0, -5.0, -3.0)
EXPOSED_PENALTIES = (-12.0, -10.0, -8.0, -6.0, -4.0, -3.0, -2.0)
SEEN_TODAY_PENALTY = -30.0


@dataclass(frozen=True)
class ScoreBreakdown:
    nutrition: float
    seasonal_wellness: float
    personal_family: float
    preference_history: float
    feasibility: float
    diversity: float
    weather_modifier: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.nutrition
            + self.seasonal_wellness
            + self.personal_family
            + self.preference_history
            + self.feasibility
            + self.diversity
        )


@dataclass(frozen=True)
class RankedCandidate:
    food: Food
    base_score: float
    breakdown: ScoreBreakdown
    reason_phrases: Mapping[str, str]
    rerank_adjustment: float = 0.0
    meal_intent_adjustment: float = 0.0
    novelty_penalty: float = 0.0
    rerank_reason: str | None = None
    selection_order: int | None = None

    @property
    def final_raw_score(self) -> float:
        return (
            self.base_score
            + self.rerank_adjustment
            + self.meal_intent_adjustment
            + self.novelty_penalty
        )

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
    exposure_counts: Mapping[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class PreferenceSnapshot:
    """从收藏与近七日选择压缩出的有界软偏好，不包含任何硬过滤。"""

    category_affinity: Mapping[str, float] = field(default_factory=dict)
    method_affinity: Mapping[str, float] = field(default_factory=dict)
    ingredient_affinity: Mapping[str, float] = field(default_factory=dict)


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
    engine_name = "rules_v4"

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
    exclude_request_id: str | None = None,
) -> RecommendationHistory:
    """把七天日志压缩成每道菜距今最近的选择与曝光天数。"""
    chosen: dict[int, int] = {}
    exposed: dict[int, int] = {}
    exposure_counts: dict[int, int] = {}
    seen_today: set[int] = set()
    for log_record in logs:
        days_ago = (as_of - log_record.log_date).days
        if 0 <= days_ago < len(CHOSEN_PENALTIES):
            for food_id in log_record.chosen_food_ids_json or []:
                _remember_nearest(chosen, food_id, days_ago)
    for event in events:
        if exclude_request_id is not None and event.request_id == exclude_request_id:
            continue
        days_ago = (as_of - event.event_date).days
        if not 0 <= days_ago < len(EXPOSED_PENALTIES):
            continue
        for food_id in set(event.recommended_food_ids_json or []):
            _remember_nearest(exposed, food_id, days_ago)
            exposure_counts[food_id] = exposure_counts.get(food_id, 0) + 1
            if days_ago == 0:
                seen_today.add(food_id)
    return RecommendationHistory(
        seen_today=frozenset(seen_today),
        chosen_days_ago=chosen,
        exposed_days_ago=exposed,
        exposure_counts=exposure_counts,
    )


def _normalized_affinity(
    counts: Counter[str],
    *,
    limit: float,
) -> dict[str, float]:
    if not counts:
        return {}
    peak = max(counts.values())
    return {
        key: round(float(value) / float(peak) * limit, 3)
        for key, value in counts.items()
    }


def build_preference_snapshot(
    foods: Sequence[Food],
    logs: Sequence[DailyLog],
    *,
    favorite_food_ids: Sequence[int],
) -> PreferenceSnapshot:
    """收藏权重略高于已选历史，但只学习相似特征，不直推原菜。"""
    by_id = {food.id: food for food in foods if food.id is not None}
    weighted_ids: Counter[int] = Counter()
    for log_record in logs:
        weighted_ids.update(log_record.chosen_food_ids_json or [])
    for food_id in favorite_food_ids:
        weighted_ids[food_id] += 2

    category_counts: Counter[str] = Counter()
    method_counts: Counter[str] = Counter()
    ingredient_counts: Counter[str] = Counter()
    for food_id, weight in weighted_ids.items():
        food = by_id.get(food_id)
        if food is None:
            continue
        category_counts[food.category] += weight
        method_counts[food.cooking_method] += weight
        for ingredient in set(food.ingredients_json or []):
            ingredient_counts[ingredient] += weight
    return PreferenceSnapshot(
        category_affinity=_normalized_affinity(category_counts, limit=3.0),
        method_affinity=_normalized_affinity(method_counts, limit=2.0),
        ingredient_affinity=_normalized_affinity(ingredient_counts, limit=2.5),
    )


def preference_history_score(food: Food, snapshot: PreferenceSnapshot) -> float:
    """15 分偏好维度：7.5 中性基准 + 最多 7.5 的相似特征加分。"""
    ingredient_hits = sorted(
        (
            snapshot.ingredient_affinity.get(ingredient, 0.0)
            for ingredient in set(food.ingredients_json or [])
        ),
        reverse=True,
    )
    ingredient_bonus = min(2.5, sum(ingredient_hits[:2]))
    score = (
        7.5
        + snapshot.category_affinity.get(food.category, 0.0)
        + snapshot.method_affinity.get(food.cooking_method, 0.0)
        + ingredient_bonus
    )
    return round(min(float(RULE_V4_WEIGHTS['preference_history']), score), 2)


def food_matches_ingredient(food: Food, ingredient: str) -> bool:
    """以保守的包含关系匹配中文食材；只用于用户明确输入的食材约束。"""
    target = ingredient.strip().casefold()
    if not target:
        return False
    for raw_value in food.ingredients_json or []:
        value = str(raw_value).strip().casefold()
        if value and (target in value or value in target):
            return True
    return False


def _meal_goal_adjustment(food: Food, goal: str | None) -> tuple[float, str]:
    nutrition = food.nutrition_json or {}
    protein = float(nutrition.get("protein_g", 0.0) or 0.0)
    fat = float(nutrition.get("fat_g", 0.0) or 0.0)
    calories = float(food.calories_kcal_per_100g or 0.0)
    if goal == "high_protein":
        if protein >= 15:
            return 2.0, "蛋白质更充足"
        return (-1.0, "") if protein < 7 else (0.0, "")
    if goal == "weight_control":
        if 0 < calories <= 180 and fat <= 10:
            return 2.0, "能量与脂肪更克制"
        return (-1.5, "") if calories > 300 or fat > 20 else (0.0, "")
    if goal == "balanced" and protein > 0:
        return 0.75, ""
    return 0.0, ""


def meal_intent_adjustment(food: Food, intent: MealIntent | None) -> tuple[float, str]:
    """把库存、时间和目标压成最多 ±6 分的软调整，绝不替代硬过滤。"""
    if intent is None:
        return 0.0, ""

    delta = 0.0
    reasons: list[str] = []
    ingredient_hits = sum(
        food_matches_ingredient(food, ingredient)
        for ingredient in intent.available_ingredients
    )
    if ingredient_hits:
        delta += min(3.0, ingredient_hits * 1.5)
        reasons.append("现有食材更好利用")

    if intent.max_time_minutes is not None and food.cooking_time_min is not None:
        overrun = food.cooking_time_min - intent.max_time_minutes
        if overrun <= 0:
            delta += 1.5
            reasons.append("符合时间预算")
        else:
            delta -= min(3.0, 1.0 + overrun / max(intent.max_time_minutes, 1))

    goal_delta, goal_reason = _meal_goal_adjustment(food, intent.goal)
    delta += goal_delta
    if goal_reason:
        reasons.append(goal_reason)

    bounded = max(-MAX_MEAL_INTENT_DELTA, min(MAX_MEAL_INTENT_DELTA, delta))
    return round(bounded, 2), "、".join(reasons[:2])


def _exploration_key(
    candidate: RankedCandidate,
    *,
    user_id: int,
    event_date: date,
    request_id: str,
    meal_role: str,
    floor_score: float,
    engine_version: str,
) -> float:
    food_id = candidate.food.id or 0
    payload = (
        f'{user_id}|{event_date.isoformat()}|{request_id}|{meal_role}|'
        f'{engine_version}|{food_id}'
    )
    digest = hashlib.sha256(payload.encode()).digest()
    uniform = (int.from_bytes(digest[:8], 'big') + 1) / (2**64 + 1)
    quality_weight = 1.0 + max(0.0, candidate.final_raw_score - floor_score)
    return -math.log(uniform) / quality_weight


def apply_bounded_exploration(
    candidates: Sequence[RankedCandidate],
    *,
    user_id: int,
    event_date: date,
    request_id: str,
    meal_role: str,
    engine_version: str = 'rules_v5',
    quality_band: float = 5.0,
) -> list[RankedCandidate]:
    """只在距角色最高分不超过 quality_band 的候选间做可复现加权探索。"""
    if not candidates:
        return []
    highest = max(candidate.final_raw_score for candidate in candidates)
    floor_score = highest - quality_band
    in_band = [candidate for candidate in candidates if candidate.final_raw_score >= floor_score]
    outside = [candidate for candidate in candidates if candidate.final_raw_score < floor_score]
    ordered = sorted(
        in_band,
        key=lambda candidate: _exploration_key(
            candidate,
            user_id=user_id,
            event_date=event_date,
            request_id=request_id,
            meal_role=meal_role,
            floor_score=floor_score,
            engine_version=engine_version,
        ),
    )
    ordered.extend(
        sorted(
            outside,
            key=lambda candidate: (-candidate.final_raw_score, candidate.food.id or 0),
        )
    )
    return [replace(candidate, selection_order=index) for index, candidate in enumerate(ordered)]


def with_client_exclusions(
    history: RecommendationHistory,
    food_ids: Sequence[int],
) -> RecommendationHistory:
    """Merge untrusted client hints into soft exposure history only."""
    return replace(
        history,
        seen_today=history.seen_today | frozenset(food_ids),
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
                repeat_count = max(1, history.exposure_counts.get(food_id, 1))
                repeat_penalty = min(12.0, float((repeat_count - 1) * 4))
                penalties.append(EXPOSED_PENALTIES[exposed_days] - repeat_penalty)
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
