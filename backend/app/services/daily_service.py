"""每日推荐日志 service - 读写 DailyLog 表。

学习点：
- DailyLog 一天一行，保存当天最新推荐与实际选择
- RecommendationEvent 一次推荐一行，供刷新轮换和七天曝光降权
- 推荐调 record_recommendation 原子更新 DailyLog 并追加事件；
  选择（T11）调 update_chosen_food_ids 写 chosen_food_ids
"""
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from app.models.daily_log import DailyLog
from app.models.recommendation_event import RecommendationEvent


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
) -> DailyLog:
    """准备当天日志但不提交，供单表与事件原子写入复用。"""
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
    """原子更新当天日志并追加一次推荐曝光事件。"""
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
    stmt = (
        select(DailyLog)
        .where(DailyLog.user_id == user_id)
        .where(DailyLog.log_date == log_date)
    )
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

    stmt = (
        select(DailyLog)
        .where(DailyLog.user_id == user_id)
        .where(DailyLog.log_date == log_date)
    )
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

    stmt = (
        select(DailyLog)
        .where(DailyLog.user_id == user_id)
        .where(DailyLog.log_date == log_date)
    )
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
