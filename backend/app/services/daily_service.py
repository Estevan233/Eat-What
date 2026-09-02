"""每日推荐日志 service - 读写 DailyLog 表。

学习点：
- DailyLog 一天一行，保存当天最新推荐与实际选择
- RecommendationEvent 一次推荐一行，供刷新轮换和七天曝光降权
- 推荐调 record_recommendation 原子更新 DailyLog 并追加事件；
  选择（T11）调 update_chosen_food_ids 写 chosen_food_ids
"""

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.core.errors import (
    AppError,
    InvalidMealChoiceError,
    MealAlreadyChosenError,
    ValidationError,
)
from app.models.daily_log import DailyLog
from app.models.recommendation_event import RecommendationEvent
from app.repositories.cloudbase_rdb import RdbFilter, RdbOrder
from app.repositories.cloudbase_repository import DatabaseSession, is_cloudbase_repository
from app.schemas.meal import MealItem, MealNutrition, MealRole, MealSnapshot, MealSubstitution

MEAL_ROLE_ORDER: tuple[MealRole, ...] = ("main", "vegetable", "staple")


def _save_cloudbase_daily_log(
    session: DatabaseSession,
    record: DailyLog,
) -> DailyLog:
    """Persist one daily projection without relying on REST upsert permissions."""
    if not is_cloudbase_repository(session):  # pragma: no cover - caller contract
        raise TypeError("CloudBase repository required")
    if record.id is None:
        return session.insert(record)
    return session.update(
        record,
        filters=(
            RdbFilter('id', 'eq', record.id),
            RdbFilter('user_id', 'eq', record.user_id),
        ),
    )


def get_recent(
    session: DatabaseSession,
    user_id: int,
    *,
    days: int = 3,
    as_of: date | None = None,
) -> list[DailyLog]:
    """取包含 as_of 当天在内的最近 N 天 DailyLog（闭区间）。

    Args:
        days: 回看天数，从 as_of 往前数 N 天（含 as_of）
        as_of: 截止日期；None 表示今天。rules_v6 用 30 天窗口时注入固定日期，
            避免函数内部读系统日期导致测试漂移。

    Returns:
        最近 days 天的 DailyLog 列表（可能为空）
    """
    end = as_of or date.today()
    start = end - timedelta(days=days - 1)
    if is_cloudbase_repository(session):
        return session.list(
            DailyLog,
            filters=(
                RdbFilter('user_id', 'eq', user_id),
                RdbFilter('log_date', 'gte', start),
                RdbFilter('log_date', 'lte', end),
            ),
            order=(RdbOrder('log_date', 'desc'),),
        )
    stmt = (
        select(DailyLog)
        .where(DailyLog.user_id == user_id)
        .where(DailyLog.log_date >= start)
        .where(DailyLog.log_date <= end)
        .order_by(DailyLog.log_date.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


def _prepare_today_log(
    session: DatabaseSession,
    user_id: int,
    *,
    log_date: date,
    meal_slot: str = "lunch",
    recommended_food_ids: Iterable[int] | None,
    mood: str,
    activity_level: str,
    weather_tag: str | None,
    dining_mode: str = "cook",
    audience: str = "personal",
    party_size: int = 1,
) -> DailyLog:
    """准备某天某餐次的推荐日志但不提交，供单表与事件原子写入复用。

    三餐化：只匹配 source='recommendation' 的行（manual 自记行不参与 upsert）。
    """
    if is_cloudbase_repository(session):
        record = session.first(
            DailyLog,
            filters=(
                RdbFilter('user_id', 'eq', user_id),
                RdbFilter('log_date', 'eq', log_date),
                RdbFilter('meal_slot', 'eq', meal_slot),
                RdbFilter('source', 'eq', 'recommendation'),
            ),
        )
    else:
        stmt = (
            select(DailyLog)
            .where(DailyLog.user_id == user_id)
            .where(DailyLog.log_date == log_date)
            .where(DailyLog.meal_slot == meal_slot)
            .where(DailyLog.source == "recommendation")
        )
        record = session.exec(stmt).first()

    rec_list = list(recommended_food_ids) if recommended_food_ids is not None else []

    now = datetime.utcnow()
    if record is None:
        return DailyLog(
            user_id=user_id,
            log_date=log_date,
            meal_slot=meal_slot,
            source="recommendation",
            recommended_food_ids_json=rec_list,
            chosen_food_ids_json=[],
            mood=mood,
            activity_level=activity_level,
            weather_tag=weather_tag,
            dining_mode=dining_mode,
            audience=audience,
            party_size=party_size,
            created_at=now,
            updated_at=now,
        )
    if recommended_food_ids is not None:
        record.recommended_food_ids_json = rec_list
    record.meal_slot = meal_slot
    record.mood = mood
    record.activity_level = activity_level
    record.weather_tag = weather_tag
    record.dining_mode = dining_mode
    record.audience = audience
    record.party_size = party_size
    record.updated_at = now
    return record


def record_recommendation(
    session: DatabaseSession,
    user_id: int,
    *,
    recommended_food_ids: Iterable[int],
    mood: str,
    activity_level: str,
    weather_tag: str | None,
    engine: str,
    recommended_meal: dict[str, Any] | None = None,
    substitutions: list[dict[str, Any]] | None = None,
    scorer_version: str | None = None,
    builder_version: str = "legacy",
    agent_name: str | None = None,
    event_date: date | None = None,
    dining_mode: str = "cook",
    audience: str = "personal",
    meal_slot: str = "lunch",
    party_size: int = 1,
    request_id: str | None = None,
    check_idempotency: bool = True,
) -> tuple[DailyLog, RecommendationEvent]:
    """原子更新当天日志并追加一次推荐曝光事件。

    同一个 request_id 的重放返回第一次写入，不覆盖日报。该约束为后续
    REST Repository 的“事件为真相、日报为投影”写入流程提供幂等基础。
    """
    normalized_request_id = _normalize_request_id(request_id)
    if request_id is not None and check_idempotency:
        existing = _load_idempotent_recommendation(
            session,
            user_id,
            normalized_request_id,
        )
        if existing is not None:
            return existing

    target_date = event_date or date.today()
    ids = list(recommended_food_ids)
    log_record = _prepare_today_log(
        session,
        user_id,
        log_date=target_date,
        meal_slot=meal_slot,
        recommended_food_ids=ids,
        mood=mood,
        activity_level=activity_level,
        weather_tag=weather_tag,
        dining_mode=dining_mode,
        audience=audience,
        party_size=party_size,
    )
    event = RecommendationEvent(
        request_id=normalized_request_id,
        user_id=user_id,
        event_date=target_date,
        recommended_food_ids_json=ids,
        primary_food_ids_json=ids,
        substitution_options_json=list(substitutions or []),
        primary_meal_json=recommended_meal,
        mood=mood,
        activity_level=activity_level,
        weather_tag=weather_tag,
        dining_mode=dining_mode,
        meal_slot=meal_slot,
        audience=audience,
        party_size=party_size,
        engine=engine,
        scorer_version=scorer_version or engine,
        builder_version=builder_version,
        agent_name=agent_name,
        summary_json=_recommendation_summary(recommended_meal, substitutions or []),
    )
    if is_cloudbase_repository(session):
        saved_event = session.insert(event)
        log_record.recommendation_event_id = saved_event.id
        log_record.recommended_meal_json = recommended_meal
        try:
            saved_log = _save_cloudbase_daily_log(session, log_record)
        except Exception as exc:
            raise AppError(
                '推荐事件已保存，今日日志投影待修复，请重试',
                'RECOMMENDATION_PROJECTION_PENDING',
                503,
            ) from exc
        return saved_log, saved_event

    session.add(event)
    try:
        session.flush()
        log_record.recommendation_event_id = event.id
        log_record.recommended_meal_json = recommended_meal
        session.add(log_record)
        session.commit()
    except IntegrityError:
        session.rollback()
        repeated = _load_idempotent_recommendation(
            session,
            user_id,
            normalized_request_id,
        )
        if repeated is not None:
            return repeated
        raise
    except Exception:
        session.rollback()
        raise
    return log_record, event


def _normalize_request_id(request_id: str | None) -> str:
    if request_id is None:
        return str(uuid4())
    normalized = request_id.strip()
    if not normalized or len(normalized) > 64:
        raise ValidationError("request_id 必须为 1 到 64 个字符")
    return normalized


def _load_idempotent_recommendation(
    session: DatabaseSession,
    user_id: int,
    request_id: str,
) -> tuple[DailyLog, RecommendationEvent] | None:
    if is_cloudbase_repository(session):
        event = session.first(
            RecommendationEvent,
            filters=(RdbFilter('request_id', 'eq', request_id),),
        )
    else:
        event = session.exec(
            select(RecommendationEvent).where(RecommendationEvent.request_id == request_id)
        ).first()
    if event is None:
        return None
    if event.user_id != user_id:
        raise ValidationError("推荐请求号已被占用")
    record = get_today(session, user_id, log_date=event.event_date, meal_slot=event.meal_slot)
    if record is None or record.recommendation_event_id != event.id:
        if is_cloudbase_repository(session):
            if record is None:
                record = DailyLog(
                    user_id=user_id,
                    log_date=event.event_date,
                    meal_slot=event.meal_slot,
                    source="recommendation",
                    created_at=event.created_at,
                )
            record.recommendation_event_id = event.id
            record.recommended_food_ids_json = list(event.recommended_food_ids_json)
            record.recommended_meal_json = event.primary_meal_json
            record.mood = event.mood
            record.activity_level = event.activity_level
            record.weather_tag = event.weather_tag
            record.dining_mode = event.dining_mode
            record.meal_slot = event.meal_slot
            record.audience = event.audience
            record.party_size = event.party_size
            record.updated_at = datetime.utcnow()
            return _save_cloudbase_daily_log(session, record), event
        raise ValidationError("推荐事件已写入，但今日日志投影待修复")
    return record, event


def _recommendation_summary(
    recommended_meal: dict[str, Any] | None,
    substitutions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if recommended_meal is None:
        return None
    return {
        "total_nutrition": recommended_meal.get("total_nutrition"),
        "estimated_time_min": recommended_meal.get("estimated_time_min"),
        "substitution_count": len(substitutions),
    }


def choose_complete_meal(
    session: DatabaseSession,
    user_id: int,
    *,
    recommendation_id: int,
    selected_food_ids: Iterable[int],
    substitutions: list[dict[str, Any]],
) -> DailyLog:
    """Validate one complete meal against an owned event and persist it once."""
    event, record = _load_choice_context(session, user_id, recommendation_id)
    selected = list(selected_food_ids)
    if record.chosen_meal_json is not None:
        if record.chosen_food_ids_json == selected:
            return record
        raise MealAlreadyChosenError()

    chosen = _build_chosen_snapshot(event, selected, substitutions)
    record.chosen_food_ids_json = selected
    record.chosen_meal_json = chosen.model_dump(mode="json")
    record.chosen_total_nutrition_json = chosen.total_nutrition.model_dump(mode="json")
    record.updated_at = datetime.utcnow()
    if is_cloudbase_repository(session):
        return _save_cloudbase_daily_log(session, record)
    session.add(record)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(record)
    return record


def _load_choice_context(
    session: DatabaseSession,
    user_id: int,
    recommendation_id: int,
) -> tuple[RecommendationEvent, DailyLog]:
    if is_cloudbase_repository(session):
        event = session.first(
            RecommendationEvent,
            filters=(
                RdbFilter('id', 'eq', recommendation_id),
                RdbFilter('user_id', 'eq', user_id),
            ),
        )
    else:
        event = session.exec(
            select(RecommendationEvent)
            .where(RecommendationEvent.id == recommendation_id)
            .where(RecommendationEvent.user_id == user_id)
        ).first()
    if event is None or event.primary_meal_json is None:
        raise InvalidMealChoiceError("推荐记录不存在、已失效或不属于当前用户")

    record = get_today(session, user_id, log_date=event.event_date, meal_slot=event.meal_slot)
    if record is None or record.recommendation_event_id != event.id:
        raise InvalidMealChoiceError("这不是当前可确认的推荐，请刷新后重试")
    return event, record


def _build_chosen_snapshot(
    event: RecommendationEvent,
    selected: list[int],
    substitutions: list[dict[str, Any]],
) -> MealSnapshot:
    if event.primary_meal_json is None:  # pragma: no cover - load 已校验
        raise RuntimeError("推荐事件缺少主餐快照")
    primary = MealSnapshot.model_validate(event.primary_meal_json)
    primary_ids = [item.food_id for item in primary.items]
    primary_roles = [item.meal_role for item in primary.items]
    if len(set(primary_roles)) != len(primary_roles):
        if substitutions:
            raise InvalidMealChoiceError("多人套餐暂不支持单道替换，请整体换一套")
        if selected != primary_ids or len(set(selected)) != len(selected):
            raise InvalidMealChoiceError("多人套餐必须完整确认本次推荐的全部菜品")
        return primary

    if len(selected) != 3 or len(set(selected)) != 3:
        raise InvalidMealChoiceError("必须且只能选择主菜、蔬菜、主食各一项")

    primary_by_role = {item.meal_role: item for item in primary.items}
    allowed_by_role = _allowed_items_by_role(event, primary_by_role)
    chosen_by_role = _resolve_selected_items(selected, allowed_by_role)
    _validate_declared_substitutions(
        primary_by_role,
        chosen_by_role,
        substitutions,
    )

    items = [chosen_by_role[role] for role in MEAL_ROLE_ORDER]
    return MealSnapshot(
        items=items,
        total_nutrition=_sum_nutrition(items),
        estimated_time_min=sum(item.prep_time_min for item in items)
        + max(item.cook_time_min for item in items),
        reason=primary.reason,
    )


def _allowed_items_by_role(
    event: RecommendationEvent,
    primary_by_role: dict[MealRole, MealItem],
) -> dict[MealRole, dict[int, MealItem]]:
    allowed: dict[MealRole, dict[int, MealItem]] = {
        role: {item.food_id: item} for role, item in primary_by_role.items()
    }
    for raw in event.substitution_options_json:
        option = MealSubstitution.model_validate(raw)
        allowed.setdefault(option.target_role, {})[option.replacement.food_id] = option.replacement
    return allowed


def _resolve_selected_items(
    selected: list[int],
    allowed_by_role: dict[MealRole, dict[int, MealItem]],
) -> dict[MealRole, MealItem]:
    chosen_by_role: dict[MealRole, MealItem] = {}
    for food_id in selected:
        matching_roles = [role for role, items in allowed_by_role.items() if food_id in items]
        if len(matching_roles) != 1:
            raise InvalidMealChoiceError(f"菜品 {food_id} 不在本次推荐或换菜范围内")
        role = matching_roles[0]
        if role in chosen_by_role:
            raise InvalidMealChoiceError(f"餐单包含重复角色: {role}")
        chosen_by_role[role] = allowed_by_role[role][food_id]

    if set(chosen_by_role) != set(MEAL_ROLE_ORDER):
        raise InvalidMealChoiceError("必须选择主菜、蔬菜、主食各一项")
    return chosen_by_role


def _validate_declared_substitutions(
    primary_by_role: dict[MealRole, MealItem],
    chosen_by_role: dict[MealRole, MealItem],
    substitutions: list[dict[str, Any]],
) -> None:
    actual_substitutions = {
        (role, item.food_id)
        for role, item in chosen_by_role.items()
        if primary_by_role[role].food_id != item.food_id
    }
    declared_substitutions = {
        (str(item["target_role"]), int(item["replacement_food_id"])) for item in substitutions
    }
    if actual_substitutions != declared_substitutions:
        raise InvalidMealChoiceError("换菜声明与最终餐单不一致")


def _sum_nutrition(items: list[MealItem]) -> MealNutrition:
    fields = ("energy_kcal", "protein_g", "fat_g", "carb_g")
    values = {
        field: round(
            sum(float(getattr(item.nutrition_per_serving, field)) for item in items),
            1,
        )
        for field in fields
    }
    return MealNutrition(**values)


def upsert_today_log(
    session: DatabaseSession,
    user_id: int,
    *,
    log_date: date | None = None,
    recommended_food_ids: Iterable[int] | None = None,
    mood: str = "neutral",
    activity_level: str = "normal",
    weather_tag: str | None = None,
) -> DailyLog:
    """有就更新推荐字段，没有就建。T10 调用。

    recommended_food_ids 提供时整体覆盖；mood/activity_level/weather_tag 也覆盖。
    chosen_food_ids 不在这里改（T11 专属）。
    """
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

    if is_cloudbase_repository(session):
        return _save_cloudbase_daily_log(session, record)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_recent_recommendation_events(
    session: DatabaseSession,
    user_id: int,
    *,
    days: int = 7,
    as_of: date | None = None,
) -> list[RecommendationEvent]:
    """读取包含 as_of 当天在内的最近 N 天推荐曝光。"""
    end = as_of or date.today()
    start = end - timedelta(days=days - 1)
    if is_cloudbase_repository(session):
        return session.list(
            RecommendationEvent,
            filters=(
                RdbFilter('user_id', 'eq', user_id),
                RdbFilter('event_date', 'gte', start),
                RdbFilter('event_date', 'lte', end),
            ),
            order=(RdbOrder('created_at', 'desc'),),
        )
    stmt = (
        select(RecommendationEvent)
        .where(RecommendationEvent.user_id == user_id)
        .where(RecommendationEvent.event_date >= start)
        .where(RecommendationEvent.event_date <= end)
        .order_by(RecommendationEvent.created_at.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


def get_today(
    session: DatabaseSession,
    user_id: int,
    *,
    log_date: date | None = None,
    meal_slot: str | None = None,
) -> DailyLog | None:
    """取某天（缺省今天）某餐次的推荐日志，不存在返回 None。T11 用。

    meal_slot 缺省时按 source='recommendation' 返回当天任意一条推荐记录
    （兼容未传餐次的旧调用方）。
    """
    if log_date is None:
        log_date = date.today()
    if is_cloudbase_repository(session):
        filters = [
            RdbFilter('user_id', 'eq', user_id),
            RdbFilter('log_date', 'eq', log_date),
            RdbFilter('source', 'eq', 'recommendation'),
        ]
        if meal_slot is not None:
            filters.append(RdbFilter('meal_slot', 'eq', meal_slot))
        return session.first(DailyLog, filters=tuple(filters))
    stmt = (
        select(DailyLog)
        .where(DailyLog.user_id == user_id)
        .where(DailyLog.log_date == log_date)
        .where(DailyLog.source == "recommendation")
    )
    if meal_slot is not None:
        stmt = stmt.where(DailyLog.meal_slot == meal_slot)
    return session.exec(stmt).first()


def get_day_logs(
    session: DatabaseSession,
    user_id: int,
    *,
    log_date: date,
) -> list[DailyLog]:
    """取某一天的全部日志行（三餐 + 自记 + 外食），按创建时间正序。"""
    if is_cloudbase_repository(session):
        return session.list(
            DailyLog,
            filters=(
                RdbFilter('user_id', 'eq', user_id),
                RdbFilter('log_date', 'eq', log_date),
            ),
            order=(RdbOrder('created_at', 'asc'),),
        )
    stmt = (
        select(DailyLog)
        .where(DailyLog.user_id == user_id)
        .where(DailyLog.log_date == log_date)
        .order_by(DailyLog.created_at.asc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


def update_chosen_food_ids(
    session: DatabaseSession,
    user_id: int,
    chosen_food_ids: Iterable[int],
    *,
    log_date: date | None = None,
    meal_slot: str | None = None,
) -> DailyLog | None:
    """T11 用：用户选了哪些菜，写入 chosen_food_ids。"""
    if log_date is None:
        log_date = date.today()

    record = get_today(session, user_id, log_date=log_date, meal_slot=meal_slot)
    if record is None:
        return None
    record.chosen_food_ids_json = list(chosen_food_ids)
    record.updated_at = datetime.utcnow()
    if is_cloudbase_repository(session):
        return _save_cloudbase_daily_log(session, record)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def append_chosen_food_id(
    session: DatabaseSession,
    user_id: int,
    food_id: int,
    *,
    log_date: date | None = None,
    meal_slot: str | None = None,
) -> DailyLog | None:
    """T11 用：用户选了一道菜，追加到 chosen_food_ids（去重）。"""
    if log_date is None:
        log_date = date.today()

    record = get_today(session, user_id, log_date=log_date, meal_slot=meal_slot)
    if record is None:
        return None
    chosen = list(record.chosen_food_ids_json)
    if food_id not in chosen:
        chosen.append(food_id)
    record.chosen_food_ids_json = chosen
    record.updated_at = datetime.utcnow()
    if is_cloudbase_repository(session):
        return _save_cloudbase_daily_log(session, record)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


# ---------------------------------------------------------------------------
# 三餐化：自记（manual）CRUD / 打卡统计 / 搜索过滤
# ---------------------------------------------------------------------------

MANUAL_SNAPSHOT_KEY = "dishes"


def build_manual_snapshot(
    dishes: list[dict[str, Any]],
    shop_name: str | None,
) -> dict[str, Any]:
    """自记记录的宽松快照结构：{"dishes": [{name, kcal?}], "shop_name"?}。

    与 recommendation 快照（MealSnapshot 结构）区分：读取时按 dishes 键识别。
    """
    snapshot: dict[str, Any] = {"dishes": dishes}
    if shop_name:
        snapshot["shop_name"] = shop_name
    return snapshot


def create_manual_log(
    session: DatabaseSession,
    user_id: int,
    *,
    log_date: date,
    meal_slot: str,
    dishes: list[dict[str, Any]],
    shop_name: str | None = None,
    note: str | None = None,
) -> DailyLog:
    """写入一条自记记录（source='manual'，永远追加，一餐可多条）。"""
    now = datetime.utcnow()
    record = DailyLog(
        user_id=user_id,
        log_date=log_date,
        meal_slot=meal_slot,
        source="manual",
        shop_name=(shop_name.strip() or None) if shop_name else None,
        note=(note.strip() or None) if note else None,
        chosen_meal_json=build_manual_snapshot(dishes, shop_name) if dishes else None,
        recommended_food_ids_json=[],
        chosen_food_ids_json=[],
        created_at=now,
        updated_at=now,
    )
    if is_cloudbase_repository(session):
        return session.insert(record)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_log_by_id(session: DatabaseSession, user_id: int, log_id: int) -> DailyLog | None:
    """按 id 取当前用户的一条日志；不存在或不属于该用户返回 None。"""
    if is_cloudbase_repository(session):
        return session.first(
            DailyLog,
            filters=(
                RdbFilter('id', 'eq', log_id),
                RdbFilter('user_id', 'eq', user_id),
            ),
        )
    stmt = (
        select(DailyLog)
        .where(DailyLog.id == log_id)
        .where(DailyLog.user_id == user_id)
    )
    return session.exec(stmt).first()


def update_log(
    session: DatabaseSession,
    user_id: int,
    log_id: int,
    *,
    meal_slot: str | None = None,
    note: str | None = None,
    dishes: list[dict[str, Any]] | None = None,
    shop_name: str | None = None,
) -> DailyLog:
    """更新一条日志。

    权限按 source 区分：recommendation 仅允许改 meal_slot/note（快照是历史事实）；
    manual 允许改全部字段。不允许改的字段被忽略（非报错，保持前端简单）。
    """
    record = get_log_by_id(session, user_id, log_id)
    if record is None:
        raise AppError("记录不存在", "DAILY_LOG_NOT_FOUND", 404)
    now = datetime.utcnow()
    if meal_slot is not None:
        record.meal_slot = meal_slot
    if note is not None:
        record.note = note.strip() or None
    if record.source == "manual":
        if dishes is not None:
            record.chosen_meal_json = build_manual_snapshot(dishes, shop_name or record.shop_name)
        if shop_name is not None:
            record.shop_name = shop_name.strip() or None
            snapshot = dict(record.chosen_meal_json or {})
            if record.shop_name:
                snapshot["shop_name"] = record.shop_name
            else:
                snapshot.pop("shop_name", None)
            record.chosen_meal_json = snapshot or None
    record.updated_at = now
    if is_cloudbase_repository(session):
        return _save_cloudbase_daily_log(session, record)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def delete_log(session: DatabaseSession, user_id: int, log_id: int) -> None:
    """删除当前用户的一条日志。"""
    if is_cloudbase_repository(session):
        filters = (
            RdbFilter('id', 'eq', log_id),
            RdbFilter('user_id', 'eq', user_id),
        )
        if session.first(DailyLog, filters=filters) is None:
            raise AppError("记录不存在", "DAILY_LOG_NOT_FOUND", 404)
        session.delete(DailyLog, filters=filters)
        return
    record = get_log_by_id(session, user_id, log_id)
    if record is None:
        raise AppError("记录不存在", "DAILY_LOG_NOT_FOUND", 404)
    session.delete(record)
    session.commit()


def compute_streak(
    session: DatabaseSession,
    user_id: int,
    *,
    as_of: date | None = None,
    max_days: int = 90,
) -> int:
    """连续打卡天数：从 as_of（缺省今天）倒推，每天有任意日志即算打卡。

    今天还没记录时从昨天开始数（打卡惯例：不打断已累计的连续天数）。
    """
    today = as_of or date.today()
    logs = get_recent(session, user_id, days=max_days, as_of=today)
    recorded = {log.log_date for log in logs}
    streak = 0
    cursor = today if today in recorded else today - timedelta(days=1)
    while cursor in recorded and streak < max_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def filter_logs_by_query(logs: list[DailyLog], query: str) -> list[DailyLog]:
    """按关键词过滤日志（Python 侧，个人级数据量足够）。

    匹配范围：快照里的菜名、店铺名、备注。空串返回原列表。
    """
    keyword = query.strip().casefold()
    if not keyword:
        return logs
    matched: list[DailyLog] = []
    for log in logs:
        haystacks = [log.shop_name or "", log.note or ""]
        snapshot = log.chosen_meal_json
        if snapshot:
            haystacks.append(str(snapshot))
        if any(keyword in text.casefold() for text in haystacks):
            matched.append(log)
    return matched
