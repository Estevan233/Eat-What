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
from sqlmodel import Session, select

from app.core.errors import InvalidMealChoiceError, MealAlreadyChosenError, ValidationError
from app.models.daily_log import DailyLog
from app.models.recommendation_event import RecommendationEvent
from app.schemas.meal import MealItem, MealNutrition, MealRole, MealSnapshot, MealSubstitution

MEAL_ROLE_ORDER: tuple[MealRole, ...] = ("main", "vegetable", "staple")


def get_recent(session: Session, user_id: int, *, days: int = 3) -> list[DailyLog]:
    """取最近 N 天的 DailyLog。

    用于推荐算法第 4 步「营养均衡」：基于用户近 N 天实际选的菜，
    计算营养偏差 → 给互补的菜加分。

    Args:
        days: 回看天数，从今天往前数 N 天（含今天）

    Returns:
        最近 days 天的 DailyLog 列表（可能为空）
    """
    today = date.today()
    start = today - timedelta(days=days - 1)
    stmt = (
        select(DailyLog)
        .where(DailyLog.user_id == user_id)
        .where(DailyLog.log_date >= start)
        .where(DailyLog.log_date <= today)
        .order_by(DailyLog.log_date.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


def _prepare_today_log(
    session: Session,
    user_id: int,
    *,
    log_date: date,
    recommended_food_ids: Iterable[int] | None,
    mood: str,
    activity_level: str,
    weather_tag: str | None,
    dining_mode: str = "cook",
    audience: str = "personal",
    party_size: int = 1,
) -> DailyLog:
    """准备当天日志但不提交，供单表与事件原子写入复用。"""
    stmt = select(DailyLog).where(DailyLog.user_id == user_id).where(DailyLog.log_date == log_date)
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
            dining_mode=dining_mode,
            audience=audience,
            party_size=party_size,
            created_at=now,
            updated_at=now,
        )
    if recommended_food_ids is not None:
        record.recommended_food_ids_json = rec_list
    record.mood = mood
    record.activity_level = activity_level
    record.weather_tag = weather_tag
    record.dining_mode = dining_mode
    record.audience = audience
    record.party_size = party_size
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
    recommended_meal: dict[str, Any] | None = None,
    substitutions: list[dict[str, Any]] | None = None,
    scorer_version: str | None = None,
    builder_version: str = "legacy",
    agent_name: str | None = None,
    event_date: date | None = None,
    dining_mode: str = "cook",
    audience: str = "personal",
    party_size: int = 1,
    request_id: str | None = None,
) -> tuple[DailyLog, RecommendationEvent]:
    """原子更新当天日志并追加一次推荐曝光事件。

    同一个 request_id 的重放返回第一次写入，不覆盖日报。该约束为后续
    REST Repository 的“事件为真相、日报为投影”写入流程提供幂等基础。
    """
    normalized_request_id = _normalize_request_id(request_id)
    if request_id is not None:
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
        audience=audience,
        party_size=party_size,
        engine=engine,
        scorer_version=scorer_version or engine,
        builder_version=builder_version,
        agent_name=agent_name,
        summary_json=_recommendation_summary(recommended_meal, substitutions or []),
    )
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
    session: Session,
    user_id: int,
    request_id: str,
) -> tuple[DailyLog, RecommendationEvent] | None:
    event = session.exec(
        select(RecommendationEvent).where(RecommendationEvent.request_id == request_id)
    ).first()
    if event is None:
        return None
    if event.user_id != user_id:
        raise ValidationError("推荐请求号已被占用")
    record = get_today(session, user_id, log_date=event.event_date)
    if record is None or record.recommendation_event_id != event.id:
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
    session: Session,
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
    session.add(record)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(record)
    return record


def _load_choice_context(
    session: Session,
    user_id: int,
    recommendation_id: int,
) -> tuple[RecommendationEvent, DailyLog]:
    event = session.exec(
        select(RecommendationEvent)
        .where(RecommendationEvent.id == recommendation_id)
        .where(RecommendationEvent.user_id == user_id)
    ).first()
    if event is None or event.primary_meal_json is None:
        raise InvalidMealChoiceError("推荐记录不存在、已失效或不属于当前用户")

    record = get_today(session, user_id, log_date=event.event_date)
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
    session: Session,
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
    """读取包含 as_of 当天在内的最近 N 天推荐曝光。"""
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


def get_today(session: Session, user_id: int, *, log_date: date | None = None) -> DailyLog | None:
    """取今天的 DailyLog，不存在返回 None。T11 用。"""
    if log_date is None:
        log_date = date.today()
    stmt = select(DailyLog).where(DailyLog.user_id == user_id).where(DailyLog.log_date == log_date)
    return session.exec(stmt).first()


def update_chosen_food_ids(
    session: Session,
    user_id: int,
    chosen_food_ids: Iterable[int],
    *,
    log_date: date | None = None,
) -> DailyLog | None:
    """T11 用：用户选了哪些菜，写入 chosen_food_ids。"""
    if log_date is None:
        log_date = date.today()

    stmt = select(DailyLog).where(DailyLog.user_id == user_id).where(DailyLog.log_date == log_date)
    record = session.exec(stmt).first()
    if record is None:
        return None
    record.chosen_food_ids_json = list(chosen_food_ids)
    record.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def append_chosen_food_id(
    session: Session,
    user_id: int,
    food_id: int,
    *,
    log_date: date | None = None,
) -> DailyLog | None:
    """T11 用：用户选了一道菜，追加到 chosen_food_ids（去重）。"""
    if log_date is None:
        log_date = date.today()

    stmt = select(DailyLog).where(DailyLog.user_id == user_id).where(DailyLog.log_date == log_date)
    record = session.exec(stmt).first()
    if record is None:
        return None
    chosen = list(record.chosen_food_ids_json)
    if food_id not in chosen:
        chosen.append(food_id)
    record.chosen_food_ids_json = chosen
    record.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
