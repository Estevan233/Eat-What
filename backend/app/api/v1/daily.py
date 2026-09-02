"""每日推荐路由 - POST /daily/recommend + choose + today + history + 日记 CRUD。

学习点：
- 登录依赖：推荐是用户个性化的，未登录直接 401
- service 层做业务逻辑，路由只负责「收请求、调 service、返响应」
- response_model 用 dict[str, Any] + success() 包，与其它路由一致
"""
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlmodel import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import AppError, NotFoundError, ValidationError
from app.core.timing import TimingTrace
from app.models.daily_log import DailyLog
from app.models.food import Food
from app.models.user import User
from app.schemas.daily import (
    ChooseRequest,
    DailyLogRead,
    HistoryResponse,
    ManualDish,
    ManualLogRequest,
    RecommendRequest,
    RecommendResponse,
    UpdateLogRequest,
    infer_meal_slot,
)
from app.services import daily_service, recommender
from app.utils.response import success

router = APIRouter(prefix="/daily", tags=["daily"])


@router.post("/recommend", response_model=dict[str, Any])
async def recommend_route(
    body: RecommendRequest,
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """POST /daily/recommend - 拿到今天 3 道菜的推荐。

    Body: RecommendRequest (mood / activity_level / lat? / lng? / meal_slot?)
    Returns: {"ok": true, "data": RecommendResponse}
    """
    if user.id is None:  # pragma: no cover - DB 行必有 id
        raise RuntimeError("get_current_user 返回的 user.id 不应为 None")

    timing = TimingTrace()
    resp: RecommendResponse = await recommender.recommend(
        session,
        user,
        body,
        timing=timing,
    )
    response.headers["Server-Timing"] = timing.header_value()
    return success(data=resp.model_dump(mode="json"))


@router.post("/choose", response_model=dict[str, Any])
def choose_route(
    body: ChooseRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """POST /daily/choose - 用户确认餐单，写入 DailyLog 快照。

    Body: ChooseRequest (food_id+meal_slot? 或 recommendation_id+selected_food_ids)
    Returns: {"ok": true, "data": DailyLogRead}
    """
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    if body.food_id is not None:
        # 兼容旧版小程序的单菜追加协议，待客户端全量升级后再移除。
        food = session.get(Food, body.food_id)
        if food is None:
            raise NotFoundError("food", body.food_id)
        log = daily_service.append_chosen_food_id(
            session,
            user.id,
            body.food_id,
            meal_slot=body.meal_slot or infer_meal_slot(),
        )
        if log is None:
            raise ValidationError("该餐次还没有推荐记录，请先获取推荐")
    else:
        if body.recommendation_id is None or body.selected_food_ids is None:  # pragma: no cover
            raise RuntimeError("ChooseRequest 已保证完整餐字段存在")
        log = daily_service.choose_complete_meal(
            session,
            user.id,
            recommendation_id=body.recommendation_id,
            selected_food_ids=body.selected_food_ids,
            substitutions=[item.model_dump(mode="json") for item in body.substitutions],
        )

    return success(data=_to_log_read(log))


@router.get("/today", response_model=dict[str, Any])
def today_route(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """GET /daily/today - 返回今天全部日志行（三餐 + 自记）。

    Returns: {"ok": true, "data": {"items": [DailyLogRead...]}}
    """
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    logs = daily_service.get_day_logs(session, user.id, log_date=date.today())
    return success(data={"items": [_to_log_read(log) for log in logs]})


@router.get("/history", response_model=dict[str, Any])
def history_route(
    days: int = Query(default=30, ge=1, le=90),
    query: str = Query(default="", max_length=64),
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """GET /daily/history - 近 N 天日志（按天分组的数据源），支持关键词搜索。

    Query: days(1-90) / query(菜名·店名·备注) / limit / offset
    Returns: {"ok": true, "data": {"items": [...], "total", "streak_days"}}
    """
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    logs = daily_service.get_recent(session, user.id, days=days)
    logs = daily_service.filter_logs_by_query(logs, query)
    total = len(logs)
    items = [_to_log_read(log) for log in logs[offset : offset + limit]]
    streak = daily_service.compute_streak(session, user.id)
    resp = HistoryResponse(items=items, total=total, streak_days=streak)
    return success(data=resp.model_dump(mode="json"))


@router.post("/logs/manual", response_model=dict[str, Any])
def create_manual_log_route(
    body: ManualLogRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """POST /daily/logs/manual - 自记落库（前端确认后的结构化数据，不再调 AI）。"""
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    log = daily_service.create_manual_log(
        session,
        user.id,
        log_date=_parse_log_date(body.log_date),
        meal_slot=body.meal_slot,
        dishes=[dish.model_dump(mode="json", exclude_none=True) for dish in body.dishes],
        shop_name=body.shop_name,
        note=body.note,
    )
    return success(data=_to_log_read(log))


@router.patch("/logs/{log_id}", response_model=dict[str, Any])
@router.put("/logs/{log_id}", response_model=dict[str, Any])
def update_log_route(
    log_id: int,
    body: UpdateLogRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """PATCH /daily/logs/{id} - 修改日志。

    recommendation 来源仅 meal_slot/note 生效；manual 来源全字段生效。
    """
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    log = daily_service.update_log(
        session,
        user.id,
        log_id,
        meal_slot=body.meal_slot,
        note=body.note,
        dishes=[dish.model_dump(mode="json", exclude_none=True) for dish in body.dishes]
        if body.dishes is not None
        else None,
        shop_name=body.shop_name,
    )
    return success(data=_to_log_read(log))


@router.delete("/logs/{log_id}", response_model=dict[str, Any])
def delete_log_route(
    log_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """DELETE /daily/logs/{id} - 删除当前用户的一条日志。"""
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    daily_service.delete_log(session, user.id, log_id)
    return success(data={"id": log_id, "deleted": True})


def _parse_log_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise AppError("日期格式应为 YYYY-MM-DD", "INVALID_LOG_DATE", 422) from exc


def _to_log_read(log: DailyLog) -> DailyLogRead:
    """DailyLog → DailyLogRead（log_date 转 ISO 字符串，manual 快照拆 manual_dishes）。"""
    snapshot = log.chosen_meal_json
    manual_dishes: list[ManualDish] | None = None
    chosen_meal: dict[str, Any] | None = None
    if snapshot and daily_service.MANUAL_SNAPSHOT_KEY in snapshot:
        manual_dishes = [
            ManualDish(name=str(dish.get("name", "")), kcal=dish.get("kcal"))
            for dish in snapshot.get("dishes", [])
            if dish.get("name")
        ]
    elif snapshot:
        chosen_meal = snapshot

    return DailyLogRead(
        id=log.id if log.id is not None else 0,
        user_id=log.user_id,
        log_date=log.log_date.isoformat() if isinstance(log.log_date, date) else str(log.log_date),
        meal_slot=log.meal_slot,
        source=log.source,
        shop_name=log.shop_name,
        note=log.note,
        recommended_food_ids=list(log.recommended_food_ids_json),
        chosen_food_ids=list(log.chosen_food_ids_json),
        recommendation_id=log.recommendation_event_id,
        recommended_meal=log.recommended_meal_json,
        chosen_meal=chosen_meal,
        manual_dishes=manual_dishes,
        chosen_total_nutrition=log.chosen_total_nutrition_json,
        mood=log.mood,
        activity_level=log.activity_level,
        weather_tag=log.weather_tag,
        dining_mode=log.dining_mode,
        audience=log.audience,
        party_size=log.party_size,
    )
