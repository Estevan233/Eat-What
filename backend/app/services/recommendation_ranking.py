"""推荐排序领域类型与纯函数。"""
import hashlib
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Literal, Protocol

from app.models.daily_log import DailyLog
from app.models.favorite import Favorite
from app.models.food import Food
from app.models.recommendation_event import RecommendationEvent
from app.schemas.daily import MealIntent

# rules_v4 历史权重，仅保留以兼容旧测试；生产评分已切换至 rules_v6 账本。
RULE_V4_WEIGHTS = {
    "nutrition": 22,
    "seasonal_wellness": 18,
    "personal_family": 20,
    "preference_history": 15,
    "feasibility": 15,
    "diversity": 10,
}
# rules_v6 基础分九个分项，合计严格 85；负责"这道菜适不适合"。
RULE_V6_BASE_WEIGHTS = {
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
# rules_v6 重排分两项，合计严格 15；负责"这一批是否新鲜且不单调"。
RULE_V6_RERANK_WEIGHTS = {"diversity": 7, "exploration": 8}
MAX_RULE_SCORE = 100.0
MAX_BASE_SCORE = 85.0
MAX_RERANK_DELTA = 10.0
MAX_MEAL_INTENT_DELTA = 6.0
# 14 天新鲜度常量在批次4替换为公式；此处暂保留 7 天数组供过渡。
CHOSEN_PENALTIES = (-30.0, -24.0, -18.0, -12.0, -8.0, -5.0, -3.0)
EXPOSED_PENALTIES = (-12.0, -10.0, -8.0, -6.0, -4.0, -3.0, -2.0)
SEEN_TODAY_PENALTY = -30.0


@dataclass(frozen=True)
class ScoreBreakdown:
    """rules_v6 基础分九个分项，total 钳制到 0..85。"""

    nutrition: float
    constitution: float
    solar_term: float
    weather: float
    preference: float
    feasibility: float
    mood: float
    activity: float
    zodiac: float

    @property
    def total(self) -> float:
        return max(
            0.0,
            min(
                MAX_BASE_SCORE,
                (
                    self.nutrition
                    + self.constitution
                    + self.solar_term
                    + self.weather
                    + self.preference
                    + self.feasibility
                    + self.mood
                    + self.activity
                    + self.zodiac
                ),
            ),
        )


@dataclass(frozen=True)
class RankedCandidate:
    food: Food
    base_score: float
    breakdown: ScoreBreakdown
    reason_phrases: Mapping[str, str]
    rerank_adjustment: float = 0.0
    meal_intent_adjustment: float = 0.0  # 兼容旧字段；rules_v6 已收进 feasibility，不再进入 final
    novelty_penalty: float = 0.0
    exploration_bonus: float = 0.0
    diversity_bonus: float = 0.0
    exposure_distance_days: int = 30
    seed_rank: int = 0
    rerank_reason: str | None = None
    selection_order: int | None = None

    @property
    def final_raw_score(self) -> float:
        return (
            self.base_score
            + self.novelty_penalty
            + self.exploration_bonus
            + self.diversity_bonus
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
    """从近 30 天收藏与选择压缩出的有界软偏好，不包含任何硬过滤。"""

    category_affinity: Mapping[str, float] = field(default_factory=dict)
    method_affinity: Mapping[str, float] = field(default_factory=dict)
    ingredient_affinity: Mapping[str, float] = field(default_factory=dict)
    tag_affinity: Mapping[str, float] = field(default_factory=dict)
    nature_affinity: Mapping[str, float] = field(default_factory=dict)
    negative_category: Mapping[str, float] = field(default_factory=dict)
    negative_method: Mapping[str, float] = field(default_factory=dict)
    negative_ingredient: Mapping[str, float] = field(default_factory=dict)
    negative_tag: Mapping[str, float] = field(default_factory=dict)
    negative_nature: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ExplicitPreferenceSignal:
    """显式负反馈输入缝：当前主链路默认传空集合，不建表/路由/UI。"""

    food_id: int
    action: Literal["not_interested", "hide"]
    occurred_on: date


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
        if 0 <= days_ago <= 29:
            for food_id in log_record.chosen_food_ids_json or []:
                _remember_nearest(chosen, food_id, days_ago)
    for event in events:
        if exclude_request_id is not None and event.request_id == exclude_request_id:
            continue
        days_ago = (as_of - event.event_date).days
        if not 0 <= days_ago <= 29:
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
    counts: Mapping[str, float],
    *,
    limit: float,
) -> dict[str, float]:
    """各特征轴按绝对权重截断到 cap，使 favorite(2.0) 与 chosen(1.0) 的
    权重差异在偏好分中可观测；冷启动（无信号）各轴为 0，回到 7.5 中性基准。"""
    return {
        key: round(min(float(value), limit), 3) for key, value in counts.items()
    }


def _recency_decay(days_ago: int) -> float:
    """近 30 天分档衰减：0–6=1.0, 7–13=0.8, 14–20=0.6, 21–29=0.4, ≥30=0。"""
    if days_ago <= 6:
        return 1.0
    if days_ago <= 13:
        return 0.8
    if days_ago <= 20:
        return 0.6
    if days_ago <= 29:
        return 0.4
    return 0.0


def build_preference_snapshot(
    foods: Sequence[Food],
    logs_30d: Sequence[DailyLog],
    favorites_30d: Sequence[Favorite],
    events_30d: Sequence[RecommendationEvent],
    *,
    as_of: date,
    negative_signals: Sequence[ExplicitPreferenceSignal] = (),
) -> PreferenceSnapshot:
    """从近 30 天收藏与选择压缩有界软偏好。

    收藏是显式正反馈（权重 2.0*decay，不衰减曝光）；选择是隐式反馈
    （权重 1.0*decay/sqrt(exposure_count)），用平方根做保守阻尼，防止
    系统反复曝光某类菜后自我证明"用户就爱这个"。曝光未选贡献 0；
    未选择不得推断为负偏好。
    """
    by_id = {food.id: food for food in foods if food.id is not None}
    exposure_counts: dict[int, int] = {}
    for event in events_30d:
        for food_id in set(event.recommended_food_ids_json or []):
            exposure_counts[food_id] = exposure_counts.get(food_id, 0) + 1

    weights: dict[int, float] = {}
    for fav in favorites_30d:
        if fav.created_at is None:
            continue
        days_ago = (as_of - fav.created_at.date()).days
        decay = _recency_decay(days_ago)
        if decay <= 0:
            continue
        weights[fav.food_id] = weights.get(fav.food_id, 0.0) + 2.0 * decay
    for log_record in logs_30d:
        days_ago = (as_of - log_record.log_date).days
        decay = _recency_decay(days_ago)
        if decay <= 0:
            continue
        for food_id in log_record.chosen_food_ids_json or []:
            expo = max(1, exposure_counts.get(food_id, 1))
            weights[food_id] = weights.get(food_id, 0.0) + 1.0 * decay / math.sqrt(expo)

    category_counts: defaultdict[str, float] = defaultdict(float)
    method_counts: defaultdict[str, float] = defaultdict(float)
    ingredient_counts: defaultdict[str, float] = defaultdict(float)
    tag_counts: defaultdict[str, float] = defaultdict(float)
    nature_counts: defaultdict[str, float] = defaultdict(float)
    for food_id, weight in weights.items():
        food = by_id.get(food_id)
        if food is None:
            continue
        category_counts[food.category] += weight
        method_counts[food.cooking_method] += weight
        nature_counts[food.nature] += weight
        tags = set(food.tags_json or [])
        if tags:
            share = weight / len(tags)
            for tag in tags:
                tag_counts[tag] += share
        ingredients = set(food.ingredients_json or [])
        if ingredients:
            share = weight / len(ingredients)
            for ingredient in ingredients:
                ingredient_counts[ingredient] += share

    neg_category: defaultdict[str, float] = defaultdict(float)
    neg_method: defaultdict[str, float] = defaultdict(float)
    neg_ingredient: defaultdict[str, float] = defaultdict(float)
    neg_tag: defaultdict[str, float] = defaultdict(float)
    neg_nature: defaultdict[str, float] = defaultdict(float)
    for signal in negative_signals:
        food = by_id.get(signal.food_id)
        if food is None:
            continue
        decay = _recency_decay((as_of - signal.occurred_on).days)
        if decay <= 0:
            continue
        base = (2.0 if signal.action == "hide" else 1.0) * decay
        neg_category[food.category] += base
        neg_method[food.cooking_method] += base
        neg_nature[food.nature] += base
        for tag in set(food.tags_json or []):
            neg_tag[tag] += base
        for ingredient in set(food.ingredients_json or []):
            neg_ingredient[ingredient] += base

    return PreferenceSnapshot(
        category_affinity=_normalized_affinity(category_counts, limit=1.5),
        method_affinity=_normalized_affinity(method_counts, limit=1.5),
        ingredient_affinity=_normalized_affinity(ingredient_counts, limit=1.0),
        tag_affinity=_normalized_affinity(tag_counts, limit=2.0),
        nature_affinity=_normalized_affinity(nature_counts, limit=1.5),
        negative_category=dict(neg_category),
        negative_method=dict(neg_method),
        negative_ingredient=dict(neg_ingredient),
        negative_tag=dict(neg_tag),
        negative_nature=dict(neg_nature),
    )


def preference_history_score(food: Food, snapshot: PreferenceSnapshot) -> float:
    """rules_v6 偏好分：7.5 中性基准 + 正 bonus(≤7.5) - 显式负 penalty(≤4)，钳到 0..15。"""
    tag_hits = sorted(
        (snapshot.tag_affinity.get(tag, 0.0) for tag in set(food.tags_json or [])),
        reverse=True,
    )
    tag_bonus = min(2.0, sum(tag_hits[:2]))
    ingredient_hits = sorted(
        (snapshot.ingredient_affinity.get(i, 0.0) for i in set(food.ingredients_json or [])),
        reverse=True,
    )
    ingredient_bonus = min(1.0, sum(ingredient_hits[:2]))
    positive = min(
        7.5,
        snapshot.category_affinity.get(food.category, 0.0)
        + snapshot.method_affinity.get(food.cooking_method, 0.0)
        + snapshot.nature_affinity.get(food.nature, 0.0)
        + tag_bonus
        + ingredient_bonus,
    )
    negative = min(
        4.0,
        max(
            snapshot.negative_category.get(food.category, 0.0),
            snapshot.negative_method.get(food.cooking_method, 0.0),
            snapshot.negative_nature.get(food.nature, 0.0),
            max(
                (snapshot.negative_tag.get(t, 0.0) for t in set(food.tags_json or [])),
                default=0.0,
            ),
            max(
                (snapshot.negative_ingredient.get(i, 0.0) for i in set(food.ingredients_json or [])),
                default=0.0,
            ),
        ),
    )
    score = max(0.0, min(float(RULE_V6_BASE_WEIGHTS["preference"]), 7.5 + positive - negative))
    return round(score, 2)


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


def _stable_seed_rank(
    *,
    user_id: int,
    event_date: date,
    request_id: str,
    food_id: int,
) -> int:
    """SHA-256(user|date|request_seed|food_id) 前 8 字节无符号整数；不用 Python hash()。"""
    payload = f'{user_id}|{event_date.isoformat()}|{request_id}|{food_id}'
    digest = hashlib.sha256(payload.encode()).digest()
    return int.from_bytes(digest[:8], 'big')


def apply_bounded_exploration(
    candidates: Sequence[RankedCandidate],
    *,
    user_id: int,
    event_date: date,
    request_id: str,
    meal_role: str,
    engine_version: str = 'rules_v6',
    quality_band: float = 5.0,
) -> list[RankedCandidate]:
    """rules_v6：每餐位 5 分质量带内、30 天未曝光候选得 exploration_bonus=8；
    按严格 tie-break（-final, -distance, seed, id）排序。diversity_bonus 由组餐器
    逐槽动态计算，此处只设 exploration 与 seed_rank。"""
    if not candidates:
        return []
    highest = max(candidate.final_raw_score for candidate in candidates)
    floor_score = highest - quality_band
    decorated: list[tuple[tuple[float, int, int, int], RankedCandidate, float, int]] = []
    for candidate in candidates:
        in_band = candidate.final_raw_score >= floor_score
        exploration = 8.0 if (in_band and candidate.exposure_distance_days >= 30) else 0.0
        seed = _stable_seed_rank(
            user_id=user_id,
            event_date=event_date,
            request_id=request_id,
            food_id=candidate.food.id or 0,
        )
        final = candidate.final_raw_score + exploration
        decorated.append(
            (
                (-final, -candidate.exposure_distance_days, seed, candidate.food.id or 0),
                candidate,
                exploration,
                seed,
            )
        )
    decorated.sort(key=lambda item: item[0])
    return [
        replace(candidate, exploration_bonus=exploration, seed_rank=seed, selection_order=index)
        for index, (_, candidate, exploration, seed) in enumerate(decorated)
    ]


def with_client_exclusions(
    history: RecommendationHistory,
    food_ids: Sequence[int],
) -> RecommendationHistory:
    """Merge untrusted client hints into soft exposure history only."""
    return replace(
        history,
        seen_today=history.seen_today | frozenset(food_ids),
    )


def _chosen_penalty(days_ago: int) -> float:
    """rules_v6 选择惩罚：当天 -45；1..13 天线性衰减；14 天及更早 0。"""
    if days_ago == 0:
        return -45.0
    if 1 <= days_ago <= 13:
        return -round(32.0 * (14 - days_ago) / 13.0, 2)
    return 0.0


def _exposed_penalty(days_ago: int, exposure_count: int) -> float:
    """rules_v6 曝光惩罚：当天 -45；1..13 天线性衰减 + 重复曝光额外扣分（封顶 12）。"""
    if days_ago == 0:
        return -45.0
    if 1 <= days_ago <= 13:
        base = -round(16.0 * (14 - days_ago) / 13.0, 2)
        repeat_extra = -min(12.0, 4.0 * (exposure_count - 1))
        return round(base + repeat_extra, 2)
    return 0.0


def apply_novelty(
    candidates: Sequence[RankedCandidate],
    history: RecommendationHistory,
    *,
    top_n: int,
) -> list[RankedCandidate]:
    """rules_v6 新鲜度：当天 -45，1..13 天公式衰减，14 天及更早 0；只取最强不叠加。

    不再在候选足够时硬删除当天曝光菜——-45 通常足以把它压到底部，安全角色
    候选不足时又能自然回补。同时为每个候选计算 30 天曝光距离（未曝光=30），
    供批次5 严格 tie-break 使用。
    """
    result: list[RankedCandidate] = []
    for candidate in candidates:
        food_id = candidate.food.id
        if food_id is None:
            continue
        chosen_days = history.chosen_days_ago.get(food_id)
        exposed_days = history.exposed_days_ago.get(food_id)
        expo = max(1, history.exposure_counts.get(food_id, 1))
        penalties: list[float] = [0.0]
        if food_id in history.seen_today or chosen_days == 0 or exposed_days == 0:
            penalties.append(-45.0)
        if chosen_days is not None and chosen_days >= 1:
            penalties.append(_chosen_penalty(chosen_days))
        if exposed_days is not None and exposed_days >= 1:
            penalties.append(_exposed_penalty(exposed_days, expo))
        penalty = min(penalties)
        if food_id in history.seen_today:
            distance = 0
        elif exposed_days is not None:
            distance = exposed_days
        else:
            distance = 30
        result.append(
            replace(
                candidate,
                novelty_penalty=penalty,
                exposure_distance_days=distance,
            )
        )
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
