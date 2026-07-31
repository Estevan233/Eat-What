"""每日推荐路由 - POST /daily/recommend + choose + today + history。

学习点：
- 登录依赖：推荐是用户个性化的，未登录直接 401
- service 层做业务逻辑，路由只负责「收请求、调 service、返响应」
- response_model 用 dict[str, Any] + success() 包，与其它路由一致
"""
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import NotFoundError, ValidationError
from app.models.daily_log import DailyLog
from app.models.food import Food
from app.models.user import User
from app.schemas.daily import (
    ChooseRequest,
    DailyLogRead,
    HistoryResponse,
    RecommendRequest,
    RecommendResponse,
)
from app.services import daily_service, recommender
from app.utils.response import success

router = APIRouter(prefix="/daily", tags=["daily"])


@router.post("/recommend", response_model=dict[str, Any])
async def recommend_route(
    body: RecommendRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """POST /daily/recommend - 拿到今天 3 道菜的推荐。

    Body: RecommendRequest (mood / activity_level / lat? / lng?)
    Returns: {"ok": true, "data": RecommendResponse}
    """
    if user.id is None:  # pragma: no cover - DB 行必有 id
        raise RuntimeError("get_current_user 返回的 user.id 不应为 None")

    resp: RecommendResponse = await recommender.recommend(session, user, body)
    return success(data=resp.model_dump(mode="json"))


@router.post("/choose", response_model=dict[str, Any])
def choose_route(
    body: ChooseRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """POST /daily/choose - 用户选了一道菜，写入 DailyLog.chosen_food_ids。

    Body: ChooseRequest (food_id)
    Returns: {"ok": true, "data": DailyLogRead}
    """
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    # 校验 food_id 存在
    food = session.get(Food, body.food_id)
    if food is None:
        raise NotFoundError("food", body.food_id)

    # 必须先有今天的推荐记录
    log = daily_service.append_chosen_food_id(session, user.id, body.food_id)
    if log is None:
        raise ValidationError("今天还没有推荐记录，请先获取推荐")

    return success(data=_to_log_read(log))


@router.get("/today", response_model=dict[str, Any])
def today_route(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """GET /daily/today - 取今天的 DailyLog，不存在返回 null。"""
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    log = daily_service.get_today(session, user.id)
    data = _to_log_read(log) if log is not None else None
    return success(data=data)


@router.get("/history", response_model=dict[str, Any])
def history_route(
    days: int = Query(default=30, ge=1, le=90),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """GET /daily/history - 近 N 天的 DailyLog 列表。

    Query: days(1-90, 默认 30)
    Returns: {"ok": true, "data": {"items": [...], "total": 5}}
    """
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    logs = daily_service.get_recent(session, user.id, days=days)
    items = [_to_log_read(log) for log in logs]
    resp = HistoryResponse(items=items, total=len(items))
    return success(data=resp.model_dump(mode="json"))


def _to_log_read(log: DailyLog) -> DailyLogRead:
    """DailyLog → DailyLogRead（log_date 转 ISO 字符串）。"""
    return DailyLogRead(
        id=log.id if log.id is not None else 0,
        user_id=log.user_id,
        log_date=log.log_date.isoformat() if isinstance(log.log_date, date) else str(log.log_date),
        recommended_food_ids=list(log.recommended_food_ids_json),
        chosen_food_ids=list(log.chosen_food_ids_json),
        mood=log.mood,
        activity_level=log.activity_level,
        weather_tag=log.weather_tag,
    )
