"""每日推荐日志 service - 读写 DailyLog 表。

学习点：
- get_recent 只读 chosen_food_ids 非空的记录（用户实际选过的菜，用于营养均衡打分）
- upsert_today_log 用 SQLite 的 INSERT OR REPLACE 语义（user_id+log_date 唯一）
- 推荐（T10）调 upsert_today_log 写 recommended_food_ids；
  选择（T11）调 update_chosen_food_ids 写 chosen_food_ids
"""
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from app.models.daily_log import DailyLog


def get_recent(session: Session, user_id: int, *, days: int = 3) -> list[DailyLog]:
    """取最近 N 天的 DailyLog，含 chosen_food_ids 非空的记录。

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
    if log_date is None:
        log_date = date.today()

    stmt = (
        select(DailyLog)
        .where(DailyLog.user_id == user_id)
        .where(DailyLog.log_date == log_date)
    )
    record = session.exec(stmt).first()

    rec_list = list(recommended_food_ids) if recommended_food_ids is not None else []

    if record is None:
        record = DailyLog(
            user_id=user_id,
            log_date=log_date,
            recommended_food_ids_json=rec_list,
            chosen_food_ids_json=[],
            mood=mood,
            activity_level=activity_level,
            weather_tag=weather_tag,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    else:
        if recommended_food_ids is not None:
            record.recommended_food_ids_json = rec_list
        record.mood = mood
        record.activity_level = activity_level
        record.weather_tag = weather_tag
        record.updated_at = datetime.utcnow()

    session.add(record)
    session.commit()
    session.refresh(record)
    return record


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
