"""Persistence service for exact private shop+dish memories."""

import unicodedata
from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.errors import NotFoundError
from app.models.dining_memory import DiningMemory
from app.schemas.dining import DiningMemoryUpsert, DiningVerdict


def normalize_identity(value: str) -> tuple[str, str]:
    display = " ".join(unicodedata.normalize("NFKC", value).split())
    return display, display.casefold()


def upsert_memory(
    session: Session,
    user_id: int,
    payload: DiningMemoryUpsert,
) -> DiningMemory:
    shop_name, shop_key = normalize_identity(payload.shop_name)
    dish_name, dish_key = normalize_identity(payload.dish_name)
    record = session.exec(
        select(DiningMemory)
        .where(DiningMemory.user_id == user_id)
        .where(DiningMemory.normalized_shop_name == shop_key)
        .where(DiningMemory.normalized_dish_name == dish_key)
    ).first()
    now = datetime.utcnow()
    if record is None:
        record = DiningMemory(
            user_id=user_id,
            shop_name=shop_name,
            dish_name=dish_name,
            normalized_shop_name=shop_key,
            normalized_dish_name=dish_key,
            verdict=payload.verdict,
            note=payload.note,
            created_at=now,
            updated_at=now,
        )
    else:
        record.shop_name = shop_name
        record.dish_name = dish_name
        record.verdict = payload.verdict
        record.note = payload.note
        record.updated_at = now
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def list_memories(
    session: Session,
    user_id: int,
    *,
    page: int,
    size: int,
    verdict: DiningVerdict | None = None,
) -> tuple[list[DiningMemory], int]:
    conditions = [DiningMemory.user_id == user_id]
    if verdict is not None:
        conditions.append(DiningMemory.verdict == verdict)
    statement = select(DiningMemory).where(*conditions)
    total = session.exec(
        select(func.count()).select_from(DiningMemory).where(*conditions)
    ).one()
    items = list(
        session.exec(
            statement
            .order_by(DiningMemory.updated_at.desc())  # type: ignore[attr-defined]
            .offset((page - 1) * size)
            .limit(size)
        ).all()
    )
    return items, int(total)


def delete_memory(session: Session, user_id: int, memory_id: int) -> None:
    record = session.exec(
        select(DiningMemory)
        .where(DiningMemory.id == memory_id)
        .where(DiningMemory.user_id == user_id)
    ).first()
    if record is None:
        raise NotFoundError("dining_memory", memory_id)
    session.delete(record)
    session.commit()


def all_memories(session: Session, user_id: int) -> list[DiningMemory]:
    return list(
        session.exec(
            select(DiningMemory)
            .where(DiningMemory.user_id == user_id)
            .order_by(DiningMemory.updated_at.desc())  # type: ignore[attr-defined]
        ).all()
    )
