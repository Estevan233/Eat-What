# Recommendation Diversity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 降低天气维度的支配程度，实现当天刷新轮换和近 7 天重复降权，并建立可安全接入 Agent 的候选重排边界。

**Architecture:** 保持现有 FastAPI 接口不变，把推荐流程拆成硬过滤、规则评分、有界重排调整、新鲜度惩罚、多样性选择和原子持久化。新增 RecommendationEvent 保存每次曝光，DailyLog 继续保存当天最新推荐与实际选择；未来 Agent 只返回候选集合内的有限调整值，失败时回退规则结果。

**Tech Stack:** Python 3.10+、FastAPI、SQLModel、SQLite/PostgreSQL、pytest、pytest-asyncio、ruff、mypy、uni-app/Vue 3。

---

## 文件结构

- Create: backend/app/models/recommendation_event.py
  - 每次成功推荐一行，保存最小化曝光上下文。
- Modify: backend/app/models/__init__.py
  - 注册 RecommendationEvent，确保 create_all 能建表。
- Modify: backend/app/services/daily_service.py
  - 查询曝光历史，并用单次事务同时更新 DailyLog、插入 RecommendationEvent。
- Create: backend/app/services/recommendation_ranking.py
  - 保存评分 DTO、Agent 重排协议、分数归一化、历史信号、新鲜度与多样性纯函数。
- Modify: backend/app/services/recommender.py
  - 重平衡规则权重并编排新推荐管线。
- Create: backend/tests/services/test_daily_service.py
  - 覆盖推荐事件、当天最新日志和查询窗口。
- Create: backend/tests/services/test_recommendation_ranking.py
  - 覆盖 Agent 调整边界、新鲜度与三阶段多样性。
- Modify: backend/tests/services/test_recommender.py
  - 覆盖新权重、连续刷新、七天历史与性能。
- Modify: backend/tests/test_api_v1/test_daily.py
  - 验证 API 兼容和“一次推荐一条事件、一天一条 DailyLog”。
- Create: miniapp/src/config/env.ts and miniapp/src/config/env.test.ts
  - 解析并测试本地模拟器与 HTTPS 预览使用的 API 基址。
- Create: miniapp/vitest.config.ts
  - 纯函数单测不加载 uni-app 构建插件，避免测试启动阶段误触小程序编译链。
- Modify: miniapp/src/api/request.ts
  - 使用统一环境配置，不再在请求层硬编码地址。
- Modify: miniapp/src/manifest.json
  - 让开发与发布构建携带当前小程序 AppID，避免生成 `touristappid`。
- Create: miniapp/.env.example and docs/guides/wechat-devtools-wsl.md
  - 记录 Windows 微信开发者工具连接 WSL 的完整调试、预览与上传流程。
- Modify: .trellis/tasks/08-11-recommendation-diversity/implement.md
  - 指向本执行计划并记录验证门槛。

## 执行约束

- project.config.json 与 project.private.config.json 是用户文件，所有 git add 命令都不得包含它们。
- 业务代码使用 TDD：先看到目标测试失败，再写最小实现。
- 下列 Commit 步骤是逻辑提交边界；按 Trellis Phase 3.4，在最终一次性展示提交方案并获用户确认前不执行 git commit。
- 当前任务不新增 Agent/LLM 依赖，不修改前端 API 类型。

### Task 0: 激活 Trellis 任务并建立实现分支

**Files:**
- Modify metadata only: .trellis/tasks/08-11-recommendation-diversity/task.json

- [ ] **Step 1: 确认真实工作副本与用户文件**

Run:

~~~bash
cd /root/miniapp-trellis
git status --short --branch
~~~

Expected:

~~~text
## main
?? project.config.json
?? project.private.config.json
~~~

- [ ] **Step 2: 创建实现分支并登记任务范围**

Run:

~~~bash
git switch -c feat/recommendation-diversity
python3 ./.trellis/scripts/task.py set-branch 08-11-recommendation-diversity feat/recommendation-diversity
python3 ./.trellis/scripts/task.py set-base-branch 08-11-recommendation-diversity main
python3 ./.trellis/scripts/task.py set-scope 08-11-recommendation-diversity backend
TRELLIS_CONTEXT_ID=codex_019fbb2f-fbdc-7310-a83c-3d038b5ef9fe \
  python3 ./.trellis/scripts/task.py start 08-11-recommendation-diversity
~~~

Expected: task status becomes in_progress and the active branch is feat/recommendation-diversity.

- [ ] **Step 3: 跑基线检查**

Run:

~~~bash
cd /root/miniapp-trellis/backend
source .venv/bin/activate
pytest tests/services/test_recommender.py tests/test_api_v1/test_daily.py -q
~~~

Expected: all existing selected tests pass before feature edits.

### Task 1: 推荐事件模型与原子持久化

**Files:**
- Create: backend/app/models/recommendation_event.py
- Modify: backend/app/models/__init__.py:1-8
- Create: backend/tests/services/test_daily_service.py
- Modify: backend/app/services/daily_service.py:9-160

- [ ] **Step 1: 写推荐事件持久化失败测试**

Create backend/tests/services/test_daily_service.py:

~~~python
from datetime import date, timedelta

from sqlmodel import select

from app.models.daily_log import DailyLog
from app.models.recommendation_event import RecommendationEvent
from app.models.user import User
from app.services import daily_service


def _create_user(session) -> User:
    user = User(openid="daily_service_user", nickname="测试用户", avatar_url=None)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_record_recommendation_keeps_events_and_latest_daily_log(session):
    user = _create_user(session)
    assert user.id is not None

    _, first = daily_service.record_recommendation(
        session,
        user.id,
        recommended_food_ids=[1, 2, 3],
        mood="neutral",
        activity_level="normal",
        weather_tag="mild",
        engine="rules_v2",
    )
    latest, second = daily_service.record_recommendation(
        session,
        user.id,
        recommended_food_ids=[4, 5, 6],
        mood="tired",
        activity_level="high",
        weather_tag="rainy",
        engine="rules_v2",
    )

    logs = list(session.exec(select(DailyLog)).all())
    events = list(
        session.exec(
            select(RecommendationEvent).order_by(RecommendationEvent.id)
        ).all()
    )
    assert len(logs) == 1
    assert logs[0].recommended_food_ids_json == [4, 5, 6]
    assert logs[0].chosen_food_ids_json == []
    assert latest.id == logs[0].id
    assert len(events) == 2
    assert {first.id, second.id} == {events[0].id, events[1].id}
    assert [event.recommended_food_ids_json for event in events] == [
        [1, 2, 3],
        [4, 5, 6],
    ]
    sensitive_fields = {"lat", "lng", "birthday", "height_cm", "weight_kg"}
    assert sensitive_fields.isdisjoint(RecommendationEvent.model_fields)


def test_get_recent_recommendation_events_respects_seven_day_window(session):
    user = _create_user(session)
    assert user.id is not None
    today = date(2026, 8, 11)
    session.add_all(
        [
            RecommendationEvent(
                user_id=user.id,
                event_date=today,
                recommended_food_ids_json=[1, 2, 3],
            ),
            RecommendationEvent(
                user_id=user.id,
                event_date=today - timedelta(days=6),
                recommended_food_ids_json=[4, 5, 6],
            ),
            RecommendationEvent(
                user_id=user.id,
                event_date=today - timedelta(days=7),
                recommended_food_ids_json=[7, 8, 9],
            ),
        ]
    )
    session.commit()

    events = daily_service.get_recent_recommendation_events(
        session,
        user.id,
        days=7,
        as_of=today,
    )
    assert {event.recommended_food_ids_json[0] for event in events} == {1, 4}
~~~

- [ ] **Step 2: 运行测试确认失败**

Run:

~~~bash
cd /root/miniapp-trellis/backend
pytest tests/services/test_daily_service.py -q
~~~

Expected: FAIL during import because app.models.recommendation_event does not exist.

- [ ] **Step 3: 创建 RecommendationEvent 并注册模型**

Create backend/app/models/recommendation_event.py:

~~~python
"""推荐曝光事件：一次成功推荐对应一行。"""
from datetime import date, datetime

from sqlalchemy import Column, Index
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class RecommendationEvent(SQLModel, table=True):
    __tablename__ = "recommendation_events"
    __table_args__ = (
        Index("ix_recommendation_events_user_date", "user_id", "event_date"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    event_date: date = Field(index=True)
    recommended_food_ids_json: list[int] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    mood: str = Field(default="neutral", max_length=16)
    activity_level: str = Field(default="normal", max_length=8)
    weather_tag: str | None = Field(default=None, max_length=16)
    engine: str = Field(default="rules_v2", max_length=32)
    created_at: datetime = Field(default_factory=datetime.utcnow)
~~~

Modify backend/app/models/__init__.py:

~~~python
from app.models.daily_log import DailyLog
from app.models.favorite import Favorite
from app.models.food import Food
from app.models.recommendation_event import RecommendationEvent
from app.models.user import User
from app.models.user_profile import UserProfile

__all__ = [
    "DailyLog",
    "Favorite",
    "Food",
    "RecommendationEvent",
    "User",
    "UserProfile",
]
~~~

- [ ] **Step 4: 实现原子写入和事件查询**

Add to backend/app/services/daily_service.py and refactor upsert_today_log to reuse _prepare_today_log:

~~~python
from app.models.recommendation_event import RecommendationEvent


def _prepare_today_log(
    session: Session,
    user_id: int,
    *,
    log_date: date,
    recommended_food_ids: Iterable[int] | None,
    mood: str,
    activity_level: str,
    weather_tag: str | None,
) -> DailyLog:
    stmt = (
        select(DailyLog)
        .where(DailyLog.user_id == user_id)
        .where(DailyLog.log_date == log_date)
    )
    record = session.exec(stmt).first()
    rec_list = list(recommended_food_ids) if recommended_food_ids is not None else []
    now = datetime.utcnow()
    if record is None:
        return DailyLog(
            user_id=user_id,
            log_date=log_date,
            recommended_food_ids_json=rec_list,
            chosen_food_ids_json=[],
            mood=mood,
            activity_level=activity_level,
            weather_tag=weather_tag,
            created_at=now,
            updated_at=now,
        )
    if recommended_food_ids is not None:
        record.recommended_food_ids_json = rec_list
    record.mood = mood
    record.activity_level = activity_level
    record.weather_tag = weather_tag
    record.updated_at = now
    return record


def record_recommendation(
    session: Session,
    user_id: int,
    *,
    recommended_food_ids: Iterable[int],
    mood: str,
    activity_level: str,
    weather_tag: str | None,
    engine: str,
    event_date: date | None = None,
) -> tuple[DailyLog, RecommendationEvent]:
    target_date = event_date or date.today()
    ids = list(recommended_food_ids)
    log_record = _prepare_today_log(
        session,
        user_id,
        log_date=target_date,
        recommended_food_ids=ids,
        mood=mood,
        activity_level=activity_level,
        weather_tag=weather_tag,
    )
    event = RecommendationEvent(
        user_id=user_id,
        event_date=target_date,
        recommended_food_ids_json=ids,
        mood=mood,
        activity_level=activity_level,
        weather_tag=weather_tag,
        engine=engine,
    )
    session.add(log_record)
    session.add(event)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(log_record)
    session.refresh(event)
    return log_record, event


def upsert_today_log(
    session: Session,
    user_id: int,
    *,
    log_date: date | None = None,
    recommended_food_ids: Iterable[int] | None = None,
    mood: str = "neutral",
    activity_level: str = "normal",
    weather_tag: str | None = None,
) -> DailyLog:
    target_date = log_date or date.today()
    record = _prepare_today_log(
        session,
        user_id,
        log_date=target_date,
        recommended_food_ids=recommended_food_ids,
        mood=mood,
        activity_level=activity_level,
        weather_tag=weather_tag,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_recent_recommendation_events(
    session: Session,
    user_id: int,
    *,
    days: int = 7,
    as_of: date | None = None,
) -> list[RecommendationEvent]:
    end = as_of or date.today()
    start = end - timedelta(days=days - 1)
    stmt = (
        select(RecommendationEvent)
        .where(RecommendationEvent.user_id == user_id)
        .where(RecommendationEvent.event_date >= start)
        .where(RecommendationEvent.event_date <= end)
        .order_by(RecommendationEvent.created_at.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())
~~~

Keep update_chosen_food_ids、append_chosen_food_id、get_today and get_recent unchanged so choose/today/history semantics remain compatible.

- [ ] **Step 5: 运行测试确认通过**

Run:

~~~bash
pytest tests/services/test_daily_service.py tests/test_api_v1/test_daily.py -q
~~~

Expected: new daily service tests pass; existing daily API tests still pass.

- [ ] **Step 6: 记录逻辑提交边界**

Planned commit:

~~~bash
git add backend/app/models/recommendation_event.py backend/app/models/__init__.py \
  backend/app/services/daily_service.py backend/tests/services/test_daily_service.py
git commit -m "feat(recommender): 记录每次推荐曝光"
~~~

### Task 2: 排名 DTO 与 Agent 有界扩展接口

**Files:**
- Create: backend/app/services/recommendation_ranking.py
- Create: backend/tests/services/test_recommendation_ranking.py

- [ ] **Step 1: 写 DTO、归一化和调整边界失败测试**

Create backend/tests/services/test_recommendation_ranking.py:

~~~python
from app.services.recommendation_ranking import (
    MAX_RULE_SCORE,
    IdentityReranker,
    RankedCandidate,
    RerankAdjustment,
    ScoreBreakdown,
    apply_rerank_adjustments,
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
    assert adjusted[0].rerank_adjustment == 15.0
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
    assert reranker.engine_name == "rules_v2"
    assert await reranker.rerank([], None) == ()
~~~

- [ ] **Step 2: 运行测试确认失败**

Run:

~~~bash
pytest tests/services/test_recommendation_ranking.py -q
~~~

Expected: FAIL because recommendation_ranking.py does not exist.

- [ ] **Step 3: 实现排名类型和 IdentityReranker**

Create backend/app/services/recommendation_ranking.py:

~~~python
"""推荐排序领域类型与纯函数。"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from app.models.food import Food

MAX_RULE_SCORE = 75.0
MAX_RERANK_DELTA = 15.0


@dataclass(frozen=True)
class ScoreBreakdown:
    weather: float
    solar_term: float
    mood: float
    nutrition: float
    constitution: float
    activity: float
    zodiac: float

    @property
    def total(self) -> float:
        return (
            self.weather
            + self.solar_term
            + self.mood
            + self.nutrition
            + self.constitution
            + self.activity
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
    engine_name = "rules_v2"

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
    candidate_ids = {candidate.food.id for candidate in candidates}
    by_id: dict[int, RerankAdjustment] = {}
    for adjustment in adjustments:
        if adjustment.food_id not in candidate_ids:
            raise ValueError(f"重排结果包含未知 food_id={adjustment.food_id}")
        if adjustment.food_id in by_id:
            raise ValueError(f"重排结果包含重复 food_id={adjustment.food_id}")
        by_id[adjustment.food_id] = adjustment

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
~~~

- [ ] **Step 4: 运行测试确认通过**

Run:

~~~bash
pytest tests/services/test_recommendation_ranking.py -q
mypy app/services/recommendation_ranking.py
~~~

Expected: all ranking tests pass and mypy reports success.

- [ ] **Step 5: 记录逻辑提交边界**

Planned commit:

~~~bash
git add backend/app/services/recommendation_ranking.py \
  backend/tests/services/test_recommendation_ranking.py
git commit -m "feat(recommender): 建立可扩展候选重排边界"
~~~

### Task 3: 重平衡规则评分

**Files:**
- Modify: backend/app/services/recommender.py:36-339
- Modify: backend/tests/services/test_recommender.py:276-365

- [ ] **Step 1: 写天气、体质与分项上限失败测试**

Add to backend/tests/services/test_recommender.py:

~~~python
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


def test_score_food_uses_seventy_five_point_breakdown():
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
    assert candidate.breakdown.weather == 15.0
    assert candidate.breakdown.solar_term == 15.0
    assert candidate.breakdown.mood == 12.0
    assert candidate.breakdown.constitution == 10.0
    assert candidate.breakdown.activity == 5.0
    assert 0.0 <= candidate.base_score <= 75.0
~~~

- [ ] **Step 2: 运行测试确认失败**

Run:

~~~bash
pytest tests/services/test_recommender.py::test_weather_score_is_capped_and_gap_is_not_dominant \
  tests/services/test_recommender.py::test_score_food_uses_seventy_five_point_breakdown -q
~~~

Expected: FAIL because current weather max is 30 and _score_food returns tuple.

- [ ] **Step 3: 修改各维度评分**

Update backend/app/services/recommender.py:

~~~python
from app.services.recommendation_ranking import RankedCandidate, ScoreBreakdown


def _weather_cold_score(food: Food) -> tuple[float, str]:
    if food.nature in ("warm", "hot"):
        return 15.0, "天冷温补"
    if food.nature in ("cold", "cool"):
        return 3.0, ""
    return 8.0, ""


def _weather_hot_score(food: Food) -> tuple[float, str]:
    if food.nature in ("cold", "cool"):
        return 15.0, "天热清润"
    if food.nature in ("warm", "hot"):
        return 3.0, ""
    return 8.0, ""


def _score_weather(food: Food, weather: WeatherData) -> tuple[float, str]:
    tag: WeatherTag = weather.weather_tag
    is_soup = food.cooking_method in ("soup", "congee")
    is_moistening = any(
        ingredient in (food.ingredients_json or [])
        for ingredient in _MOISTENING_INGREDIENTS
    )
    if tag == "rainy":
        return (15.0, "雨天暖胃") if is_soup else (8.0, "")
    if tag == "snowy":
        return (15.0, "雪天暖性") if is_soup or food.nature in ("warm", "hot") else (6.0, "")
    if tag == "dry":
        return (15.0, "干燥润燥") if is_moistening else (8.0, "")
    if tag == "cold":
        return _weather_cold_score(food)
    if tag == "hot":
        return _weather_hot_score(food)
    return 8.0, ""


def _score_constitution(
    food: Food,
    profile: UserProfile | None,
) -> tuple[float, str]:
    constitutions = set(_parse_constitution_types(profile))
    suitable = set(food.suitable_constitutions_json or [])
    if not constitutions or not suitable:
        return 5.0, ""
    if constitutions & suitable:
        return 10.0, "适合你的体质"
    return 0.0, ""


def _score_activity(food: Food, activity_level: ActivityLevel) -> float:
    nutrition = food.nutrition_json or {}
    if activity_level == "high":
        protein_g = float(nutrition.get("protein_g", 0.0) or 0.0)
        return 5.0 if protein_g >= HIGH_PROTEIN_THRESHOLD else 0.0
    if activity_level == "light":
        fat_g = float(nutrition.get("fat_g", 0.0) or 0.0)
        return 3.0 if fat_g <= LOW_FAT_THRESHOLD else 0.0
    return 0.0
~~~

Replace the remaining score functions with:

~~~python
def _score_solar_term(food: Food, today: TodayContext) -> tuple[float, str]:
    food_terms = set(food.seasonal_solar_terms_json or [])
    if not food_terms:
        return 0.0, ""
    if today.solar_term_current:
        current = SOLAR_TERM_ZH_TO_PINYIN.get(today.solar_term_current, "")
        if current and current in food_terms:
            return 15.0, f"正值{today.solar_term_current}"
    next_term = SOLAR_TERM_ZH_TO_PINYIN.get(today.solar_term_next_name, "")
    if next_term and next_term in food_terms:
        return 8.0, f"临近{today.solar_term_next_name}"
    return 0.0, ""


def _score_zodiac(food: Food, today: TodayContext) -> tuple[float, str]:
    element = ZODIAC_ELEMENTS.get(today.zodiac_sign, "")
    preferred = ZODIAC_TAG_PREFERENCE.get(element, ())
    matched = set(food.tags_json or []) & set(preferred)
    return (3.0, "") if matched else (0.0, "")


def _score_mood(food: Food, mood: Mood) -> tuple[float, str]:
    pref = MOOD_PREFERENCE.get(mood, {})
    if not pref:
        return 0.0, ""
    nutrition = food.nutrition_json or {}
    protein_g = float(nutrition.get("protein_g", 0.0) or 0.0)
    hit = False
    min_protein = float(pref.get("min_protein_g", 0.0) or 0.0)
    if min_protein and protein_g >= min_protein:
        hit = True
    if pref.get("tag") == "soup" and food.cooking_method in ("soup", "congee"):
        hit = True
    target_ingredients = pref.get("ingredients_any")
    if target_ingredients and any(
        ingredient in (food.ingredients_json or [])
        for ingredient in target_ingredients
    ):
        hit = True
    description = str(pref.get("desc", ""))
    return (12.0, description) if hit else (0.0, "")


def _score_nutrition_balance_with_foods(
    food: Food,
    history: list[DailyLog],
    all_foods: list[Food],
) -> tuple[float, str]:
    chosen_ids = [
        food_id
        for log_record in history
        for food_id in (log_record.chosen_food_ids_json or [])
    ]
    if not chosen_ids:
        return 8.0, ""
    foods_by_id = {
        item.id: item
        for item in all_foods
        if item.id is not None
    }
    total_fat = sum(
        float(
            (foods_by_id[food_id].nutrition_json or {}).get("fat_g", 0.0)
            or 0.0
        )
        for food_id in chosen_ids
        if food_id in foods_by_id
    )
    food_fat = float((food.nutrition_json or {}).get("fat_g", 0.0) or 0.0)
    if total_fat >= RECENT_HIGH_FAT_TOTAL and food_fat <= LOW_FAT_THRESHOLD:
        return 15.0, "与你近三天偏油腻饮食互补"
    return 8.0, ""
~~~

Delete LOW_PROTEIN_THRESHOLD and RECENT_HIGH_PROTEIN_TOTAL because V2 no longer treats a high-protein history as a nutritional defect. Replace _score_food with:

~~~python
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
    weather_score, weather_phrase = _score_weather(food, weather)
    solar_score, solar_phrase = _score_solar_term(food, today)
    zodiac_score, zodiac_phrase = _score_zodiac(food, today)
    mood_score, mood_phrase = _score_mood(food, mood)
    nutrition_score, nutrition_phrase = _score_nutrition_balance_with_foods(
        food,
        history,
        all_foods,
    )
    constitution_score, constitution_phrase = _score_constitution(food, profile)
    activity_score = _score_activity(food, activity_level)
    breakdown = ScoreBreakdown(
        weather=weather_score,
        solar_term=solar_score,
        mood=mood_score,
        nutrition=nutrition_score,
        constitution=constitution_score,
        activity=activity_score,
        zodiac=zodiac_score,
    )
    return RankedCandidate(
        food=food,
        base_score=breakdown.total,
        breakdown=breakdown,
        reason_phrases={
            "weather": weather_phrase,
            "solar_term": solar_phrase,
            "zodiac": zodiac_phrase,
            "mood": mood_phrase,
            "nutrition": nutrition_phrase,
            "constitution": constitution_phrase,
        },
    )
~~~

Update _make_reason so the constitution phrase participates in explanations:

~~~python
constitution_phrase = phrases.get("constitution", "")
if constitution_phrase:
    parts.append(constitution_phrase)
~~~

- [ ] **Step 4: 运行评分回归测试**

Run:

~~~bash
pytest tests/services/test_recommender.py -q
~~~

Expected: new scoring tests pass; existing weather、节气、心情、营养和硬过滤 tests pass except the old same-input stability test, which is replaced in Task 6.

- [ ] **Step 5: 记录逻辑提交边界**

Planned commit:

~~~bash
git add backend/app/services/recommender.py backend/tests/services/test_recommender.py
git commit -m "feat(recommender): 重平衡天气与个性化评分"
~~~

### Task 4: 七天历史信号与当天轮换

**Files:**
- Modify: backend/app/services/recommendation_ranking.py
- Modify: backend/tests/services/test_recommendation_ranking.py

- [ ] **Step 1: 写历史信号和惩罚失败测试**

Add to backend/tests/services/test_recommendation_ranking.py:

~~~python
from datetime import date, timedelta

import pytest

from app.models.daily_log import DailyLog
from app.models.recommendation_event import RecommendationEvent
from app.services.recommendation_ranking import (
    apply_novelty,
    build_recommendation_history,
)


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
~~~

- [ ] **Step 2: 运行测试确认失败**

Run:

~~~bash
pytest tests/services/test_recommendation_ranking.py -q
~~~

Expected: FAIL because history and novelty functions do not exist.

- [ ] **Step 3: 实现七天历史与新鲜度惩罚**

Add to backend/app/services/recommendation_ranking.py:

~~~python
from datetime import date

from app.models.daily_log import DailyLog
from app.models.recommendation_event import RecommendationEvent

CHOSEN_PENALTIES = (-30.0, -24.0, -18.0, -12.0, -8.0, -5.0, -3.0)
EXPOSED_PENALTIES = (-12.0, -10.0, -8.0, -6.0, -4.0, -3.0, -2.0)
SEEN_TODAY_PENALTY = -30.0


@dataclass(frozen=True)
class RecommendationHistory:
    seen_today: frozenset[int]
    chosen_days_ago: Mapping[int, int]
    exposed_days_ago: Mapping[int, int]


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
~~~

- [ ] **Step 4: 运行测试确认通过**

Run:

~~~bash
pytest tests/services/test_recommendation_ranking.py -q
~~~

Expected: all ranking tests pass.

- [ ] **Step 5: 记录逻辑提交边界**

Planned commit:

~~~bash
git add backend/app/services/recommendation_ranking.py \
  backend/tests/services/test_recommendation_ranking.py
git commit -m "feat(recommender): 增加当天轮换与七天重复降权"
~~~

### Task 5: 全候选多样性选择

**Files:**
- Modify: backend/app/services/recommendation_ranking.py
- Modify: backend/tests/services/test_recommendation_ranking.py
- Modify: backend/app/services/recommender.py:342-382

- [ ] **Step 1: 写三阶段多样性失败测试**

Add to backend/tests/services/test_recommendation_ranking.py:

~~~python
from app.services.recommendation_ranking import select_diverse


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
~~~

- [ ] **Step 2: 运行测试确认失败**

Run:

~~~bash
pytest tests/services/test_recommendation_ranking.py -q
~~~

Expected: FAIL because select_diverse does not exist.

- [ ] **Step 3: 实现全候选三阶段选择**

Add to backend/app/services/recommendation_ranking.py:

~~~python
def select_diverse(
    candidates: Sequence[RankedCandidate],
    *,
    top_n: int,
) -> list[RankedCandidate]:
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

    def add(candidate: RankedCandidate) -> None:
        selected.append(candidate)
        if candidate.food.id is not None:
            selected_ids.add(candidate.food.id)
        categories.add(candidate.food.category)
        methods.add(candidate.food.cooking_method)

    for candidate in ordered:
        if len(selected) >= top_n:
            break
        if candidate.food.category in categories:
            continue
        if candidate.food.cooking_method in methods:
            continue
        add(candidate)

    for candidate in ordered:
        if len(selected) >= top_n:
            break
        if candidate.food.id in selected_ids:
            continue
        if candidate.food.category in categories:
            continue
        add(candidate)

    for candidate in ordered:
        if len(selected) >= top_n:
            break
        if candidate.food.id in selected_ids:
            continue
        add(candidate)

    return selected
~~~

Delete the old _ensure_diversity function from recommender.py; all selection must use select_diverse over the complete candidate list.

- [ ] **Step 4: 运行测试确认通过**

Run:

~~~bash
pytest tests/services/test_recommendation_ranking.py -q
~~~

Expected: all ranking tests pass.

- [ ] **Step 5: 记录逻辑提交边界**

Planned commit:

~~~bash
git add backend/app/services/recommendation_ranking.py \
  backend/tests/services/test_recommendation_ranking.py \
  backend/app/services/recommender.py
git commit -m "feat(recommender): 从完整候选池执行多样性重排"
~~~

### Task 6: 接入推荐主流程并保持 API 兼容

**Files:**
- Modify: backend/app/services/recommender.py:417-522
- Modify: backend/tests/services/test_recommender.py:406-418
- Modify: backend/tests/test_api_v1/test_daily.py:274-319

- [ ] **Step 1: 把稳定性测试改为轮换测试**

Replace test_stable_result_for_same_input in backend/tests/services/test_recommender.py:

~~~python
@pytest.mark.asyncio
async def test_refresh_rotates_results_when_six_unseen_foods_exist(
    session,
    seeded_session,
    monkeypatch,
):
    user, _ = seeded_session
    _patch_external(monkeypatch, solar_term_current="立秋")
    req = RecommendRequest(mood="neutral")

    first = await recommender.recommend(session, user, req)
    second = await recommender.recommend(session, user, req)

    first_ids = {food.id for food in first.foods}
    second_ids = {food.id for food in second.foods}
    assert first_ids.isdisjoint(second_ids)
~~~

Add an API persistence assertion to test_recommend_writes_daily_log:

~~~python
from app.models.recommendation_event import RecommendationEvent

events = list(
    session.exec(
        select(RecommendationEvent).where(RecommendationEvent.user_id == user_id)
    ).all()
)
assert len(events) == 1
assert events[0].recommended_food_ids_json == log.recommended_food_ids_json
~~~

- [ ] **Step 2: 运行测试确认失败**

Run:

~~~bash
pytest tests/services/test_recommender.py::test_refresh_rotates_results_when_six_unseen_foods_exist \
  tests/test_api_v1/test_daily.py::test_recommend_writes_daily_log -q
~~~

Expected: rotation test fails because current code returns the same batch; API event assertion fails because recommender still calls upsert_today_log.

- [ ] **Step 3: 编排新推荐管线**

Update imports and replace recommend in backend/app/services/recommender.py with the following flow:

~~~python
from datetime import date, datetime, timedelta, timezone

from app.services.recommendation_ranking import (
    CandidateReranker,
    IdentityReranker,
    RecommendationRankingContext,
    apply_novelty,
    apply_rerank_adjustments,
    build_recommendation_history,
    select_diverse,
)


async def recommend(
    session: Session,
    user: User,
    req: RecommendRequest,
    *,
    reranker: CandidateReranker | None = None,
) -> RecommendResponse:
    if user.id is None:
        raise RuntimeError("user.id 不应为 None")

    if profile_service.get_profile(session, user.id) is None:
        raise NotFoundError("user_profile", user.id)
    profile = session.exec(
        select(UserProfile).where(UserProfile.user_id == user.id)
    ).first()
    if profile is None:
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
    kept = [food for food in foods if not _is_forbidden(food, profile, req)]
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
        solar_term=today_context.solar_term_current
        or today_context.solar_term_next_name,
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
        engine_name = "rules_v2"

    ranking_history = build_recommendation_history(
        history_7d,
        events_7d,
        as_of=today,
    )
    fresh_candidates = apply_novelty(candidates, ranking_history, top_n=3)
    top3 = select_diverse(fresh_candidates, top_n=3)
    rec_ids = [
        candidate.food.id
        for candidate in top3
        if candidate.food.id is not None
    ]
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

    response_foods: list[FoodWithReason] = []
    for candidate in top3:
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
        context=RecommendContext(weather=weather, today=today_context),
    )
~~~

Keep the broad exception only around the optional reranker call and output validation. Database、weather、scoring and persistence exceptions must continue to propagate normally.

- [ ] **Step 4: 增加四批轮换和七天选择回归**

Add to backend/tests/services/test_recommender.py:

~~~python
from app.models.recommendation_event import RecommendationEvent
from app.services.recommendation_ranking import RerankAdjustment


@pytest.mark.asyncio
async def test_four_refreshes_return_twelve_unique_foods_when_pool_allows(
    session,
    seeded_session,
    monkeypatch,
):
    user, foods = seeded_session
    for index in range(3):
        food = _make_food(
            f"扩展菜{index}",
            category=f"extra_{index}",
            cooking_method=f"method_{index}",
        )
        session.add(food)
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
    assert event.engine == "rules_v2"
~~~

- [ ] **Step 5: 运行服务与 API 回归**

Run:

~~~bash
pytest tests/services/test_recommender.py \
  tests/services/test_recommendation_ranking.py \
  tests/services/test_daily_service.py \
  tests/test_api_v1/test_daily.py -q
~~~

Expected: all selected tests pass and response JSON remains unchanged.

- [ ] **Step 6: 记录逻辑提交边界**

Planned commit:

~~~bash
git add backend/app/services/recommender.py \
  backend/tests/services/test_recommender.py \
  backend/tests/test_api_v1/test_daily.py
git commit -m "feat(recommender): 接入轮换推荐管线"
~~~

### Task 7: 性能、全量质量门槛与本地验证

**Files:**
- Modify: backend/tests/services/test_recommender.py
- Modify: .trellis/tasks/08-11-recommendation-diversity/implement.md

- [ ] **Step 1: 增加 200 道菜服务性能测试**

Add to backend/tests/services/test_recommender.py:

~~~python
from time import perf_counter


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
    session.add_all(
        [
            _make_food(
                f"性能菜{index}",
                category=f"category_{index % 12}",
                cooking_method=f"method_{index % 10}",
                tags=["easy"],
            )
            for index in range(200)
        ]
    )
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
~~~

- [ ] **Step 2: 运行性能测试**

Run:

~~~bash
pytest tests/services/test_recommender.py::test_two_hundred_food_recommendation_finishes_under_half_second -q
~~~

Expected: PASS with elapsed time below 0.5 seconds.

- [ ] **Step 3: 运行后端完整质量检查**

Run:

~~~bash
cd /root/miniapp-trellis/backend
ruff check app/ tests/
mypy app/
pytest tests/ -q
~~~

Expected: ruff、mypy and all pytest tests pass.

- [ ] **Step 4: 验证前端契约和两种构建目标**

Run:

~~~bash
cd /root/miniapp-trellis/miniapp
npm run lint:check
npm run type-check
npm run build:h5
npm run build:mp-weixin
~~~

Expected: all four commands exit 0. H5 output remains under dist/build/h5; WeChat output contains dist/build/mp-weixin/app.json.

- [ ] **Step 5: H5 手工验收**

1. 启动 backend 与 npm run dev:h5。
2. 打开 http://localhost:5173/#/ 并进入今日推荐页。
3. 使用同一心情、活动量连续点击四次。
4. 候选充足时记录的 12 道菜名不重复；每批优先显示不同品类和做法。
5. 确认天气标签仍显示，但雨天不再固定出现三道汤粥。
6. 点击“就吃这个”后再次刷新，已选菜不应重新出现。

- [ ] **Step 6: 执行 Trellis 全范围检查**

Run:

~~~bash
cd /root/miniapp-trellis
python3 ./.trellis/scripts/get_context.py --mode packages
python3 ./.trellis/scripts/task.py validate 08-11-recommendation-diversity
git diff --check
git status --short
~~~

Expected: task validation and diff check pass; status only包含本任务文件与用户的两个未跟踪微信配置。

- [ ] **Step 7: 准备最终提交方案，不直接提交**

Proposed logical commits:

~~~text
1. feat(recommender): 记录每次推荐曝光
2. feat(recommender): 建立可扩展候选重排边界
3. feat(recommender): 重平衡天气与个性化评分
4. feat(recommender): 增加当天轮换与七天重复降权
5. feat(recommender): 从完整候选池执行多样性重排
6. feat(recommender): 接入轮换推荐管线
7. test(recommender): 补齐性能与全流程回归
~~~

在 Trellis Phase 3.4 向用户展示实际 dirty files 与最终提交分组；明确排除 project.config.json 和 project.private.config.json，收到一次性确认后再执行提交。

### Task 8: 微信开发者工具与 WSL 调试支持

**Files:**
- Create: miniapp/src/config/env.ts
- Create: miniapp/src/config/env.test.ts
- Create: miniapp/vitest.config.ts
- Modify: miniapp/src/api/request.ts:25-52
- Modify: miniapp/src/manifest.json
- Create: miniapp/.env.example
- Create: docs/guides/wechat-devtools-wsl.md

- [ ] **Step 1: 写 API 基址失败测试**

Create miniapp/src/config/env.test.ts:

~~~typescript
import { describe, expect, it } from 'vitest'
import { resolveApiBaseUrl } from './env'

describe('resolveApiBaseUrl', () => {
  it('uses the WSL localhost backend during local development', () => {
    expect(resolveApiBaseUrl(undefined)).toBe('http://localhost:8000')
  })

  it('uses an HTTPS preview backend and removes trailing slashes', () => {
    expect(resolveApiBaseUrl(' https://api.example.com/// ')).toBe(
      'https://api.example.com',
    )
  })
})
~~~

- [ ] **Step 2: 运行测试确认失败**

Run:

~~~bash
cd /root/miniapp-trellis/miniapp
npm test -- src/config/env.test.ts
~~~

Expected: FAIL because src/config/env.ts does not exist.

- [ ] **Step 3: 实现环境配置并接入请求层**

Create miniapp/src/config/env.ts:

~~~typescript
const LOCAL_API_BASE_URL = 'http://localhost:8000'

export function resolveApiBaseUrl(value?: string): string {
  const resolved = value?.trim() || LOCAL_API_BASE_URL
  return resolved.replace(/\/+$/, '')
}

export const API_BASE_URL = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL,
)
~~~

Modify miniapp/src/api/request.ts:

~~~typescript
import { API_BASE_URL } from '@/config/env'

// 删除原有 BASE_URL 常量，并改用：
url: API_BASE_URL + opts.url,
~~~

Create miniapp/.env.example:

~~~dotenv
# 微信开发者工具模拟器
VITE_API_BASE_URL=http://localhost:8000

# 扫码预览/真机联调使用已部署并加入微信 request 合法域名的 HTTPS 地址
# VITE_API_BASE_URL=https://api.example.com
~~~

- [ ] **Step 4: 运行前端测试与类型检查**

Run:

~~~bash
npm test -- src/config/env.test.ts
npm run type-check
~~~

Expected: both commands exit 0.

- [ ] **Step 5: 编写 Windows + WSL 操作文档**

Create docs/guides/wechat-devtools-wsl.md with these sections:

1. WSL 后端命令：uvicorn app.main:app --reload --host 0.0.0.0 --port 8000。
2. WSL 小程序监听构建命令：npm run dev:mp-weixin。
3. Windows 访问 http://localhost:8000/health 验证 WSL 转发。
4. 微信开发者工具导入路径：
   \\wsl.localhost\Ubuntu-22.04\root\miniapp-trellis\miniapp\dist\dev\mp-weixin
5. 强调 app.json 必须位于所选目录根部，不能导入仓库根目录或 miniapp/src。
6. 本地模拟器勾选“不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书”。
7. 使用 Console、Network、AppData 和 Sources 断点排查登录、推荐与选择请求。
8. 手机的 localhost 是手机自身；扫码端到端预览必须配置 HTTPS API、重新构建，并在微信公众平台加入 request 合法域名。
9. 发布使用 npm run build:mp-weixin 和 dist/build/mp-weixin，上传前恢复域名校验。
10. 常见错误：app.json not found、request:fail、401、404、模拟器正常但手机失败。

- [ ] **Step 6: 验证开发与发布输出**

Run:

~~~bash
npm run build:h5
npm run build:mp-weixin
test -f dist/build/mp-weixin/app.json
~~~

Expected: all commands exit 0 and app.json exists.

- [ ] **Step 7: 记录逻辑提交边界**

Planned commit:

~~~bash
git add miniapp/src/config/env.ts miniapp/src/config/env.test.ts \
  miniapp/src/api/request.ts miniapp/.env.example \
  docs/guides/wechat-devtools-wsl.md
git commit -m "docs(miniapp): 补齐 WSL 微信调试与预览流程"
~~~

## 完成判定

- RecommendationEvent 表已注册并随 create_all 创建。
- 每次推荐新增事件，DailyLog 一天仍只有一条且保存最新批次。
- 天气分最高 15、最大差值 12。
- 同天候选充足时连续刷新不重复。
- 近七天选择和曝光惩罚按设计衰减且不重复累加。
- 完整候选执行三阶段多样性选择。
- Agent 接口只接受候选 ID 的 [-15, 15] 调整，异常回退规则结果。
- API 请求与响应结构保持兼容。
- 后端 lint、mypy、完整 pytest，前端 lint/type-check/H5/微信构建全部通过。
- API 基址可配置，且有 Windows 微信开发者工具连接 WSL 的调试和预览文档。
