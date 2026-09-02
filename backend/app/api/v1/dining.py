"""External dining suggestions and private memories."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import AppError
from app.models.user import User
import structlog

from app.schemas.dining import (
    CitySpecialtiesResponse,
    DiningMemoryList,
    DiningMemoryRead,
    DiningMemoryUpsert,
    DiningVerdict,
    ExternalDiningRequest,
    ExternalDiningResponse,
)
from app.services import dining_memory_service, external_dining
from app.services.specialty_dishes_service import get_specialties
from app.utils.response import success

log = structlog.get_logger()
router = APIRouter(prefix="/dining", tags=["dining"])


@router.post("/recommend", response_model=dict[str, Any])
def recommend_external_route(
    body: ExternalDiningRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")
    response: ExternalDiningResponse = external_dining.recommend_external(
        session,
        user.id,
        body,
    )
    return success(data=response.model_dump(mode="json"))


@router.put("/memories", response_model=dict[str, Any])
def upsert_memory_route(
    body: DiningMemoryUpsert,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")
    record = dining_memory_service.upsert_memory(session, user.id, body)
    return success(data=DiningMemoryRead.model_validate(record).model_dump(mode="json"))


@router.get("/memories", response_model=dict[str, Any])
def list_memories_route(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=50),
    verdict: DiningVerdict | None = None,
    query: str = Query(default="", max_length=64),
    date_filter: str | None = Query(default=None, alias="date", max_length=10),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")
    target_date: date | None = None
    if date_filter:
        try:
            target_date = date.fromisoformat(date_filter)
        except ValueError as exc:
            raise AppError("日期格式应为 YYYY-MM-DD", "INVALID_DATE", 422) from exc
    items, total = dining_memory_service.list_memories(
        session,
        user.id,
        page=page,
        size=size,
        verdict=verdict,
        query=query,
        target_date=target_date,
    )
    payload = DiningMemoryList(
        items=[DiningMemoryRead.model_validate(item) for item in items],
        page=page,
        size=size,
        total=total,
    )
    return success(data=payload.model_dump(mode="json"))


@router.delete("/memories/{memory_id}", response_model=dict[str, Any])
def delete_memory_route(
    memory_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")
    dining_memory_service.delete_memory(session, user.id, memory_id)
    return success(data={"deleted": True})


@router.get("/specialties", response_model=dict[str, Any])
def list_city_specialties(
    city: str = Query(..., min_length=1, max_length=64),
) -> dict[str, object]:
    """获取某城市的本地特色菜推荐（缓存 / AI / 兜底目录）。"""
    result = get_specialties(city)
    try:
        CitySpecialtiesResponse.model_validate(result)
    except Exception as exc:
        log.warning("specialty_response_validation_failed", error=str(exc), result=result)
        return success(
            data={
                "city": result.get("city", city),
                "items": [],
                "source": "fallback",
                "degraded": True,
            }
        )
    return success(data=result)
