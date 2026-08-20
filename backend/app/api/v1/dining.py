"""External dining suggestions and private memories."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.dining import (
    DiningMemoryList,
    DiningMemoryRead,
    DiningMemoryUpsert,
    DiningVerdict,
    ExternalDiningRequest,
    ExternalDiningResponse,
)
from app.services import dining_memory_service, external_dining
from app.utils.response import success

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
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")
    items, total = dining_memory_service.list_memories(
        session,
        user.id,
        page=page,
        size=size,
        verdict=verdict,
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
