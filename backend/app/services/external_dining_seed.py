"""Idempotent import for the audited external dining candidate seed."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from sqlmodel import Session, select

from app.models.external_dining_candidate import ExternalDiningCandidate
from app.repositories.cloudbase_rdb import RdbFilter
from app.repositories.cloudbase_repository import (
    CloudBaseRepository,
    DatabaseSession,
    is_cloudbase_repository,
)
from app.services.food_seed import resolve_seed_path

DEFAULT_SEED_PATH = resolve_seed_path("external_dining_seed.json", module_file=__file__)


def _rows(session: DatabaseSession) -> list[ExternalDiningCandidate]:
    if is_cloudbase_repository(session):
        return session.list(ExternalDiningCandidate, limit=1000)
    return list(session.exec(select(ExternalDiningCandidate)).all())


def _as_string_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} 必须是字符串列表")
    return cast(list[str], value)


def _build(item: dict[str, object]) -> ExternalDiningCandidate:
    source_checked_at = datetime.fromisoformat(str(item["source_checked_at"]))
    reviewed_at_raw = item.get("reviewed_at")
    return ExternalDiningCandidate(
        catalog_key=str(item["catalog_key"]),
        legacy_key=str(item["legacy_key"]) if item.get("legacy_key") else None,
        dish_name=str(item["dish_name"]),
        aliases_json=_as_string_list(item.get("aliases", []), field="aliases"),
        category=str(item["category"]),
        meal_family=str(item["meal_family"]),
        sub_family=str(item["sub_family"]),
        cuisine_region=str(item["cuisine_region"]),
        staple_type=str(item["staple_type"]),
        protein_types_json=_as_string_list(item["protein_types"], field="protein_types"),
        serving_style=str(item["serving_style"]),
        meal_periods_json=_as_string_list(item["meal_periods"], field="meal_periods"),
        delivery_fit=str(item["delivery_fit"]),
        price_band=str(item["price_band"]),
        nature=str(item["nature"]),
        seasonal_solar_terms_json=_as_string_list(item["seasonal_solar_terms"], field="seasonal_solar_terms"),
        source_url=str(item["source_url"]),
        source_type=str(item["source_type"]),
        source_checked_at=source_checked_at,
        nutrition_source_url=str(item["nutrition_source_url"]) if item.get("nutrition_source_url") else None,
        nutrition_basis=str(item["nutrition_basis"]) if item.get("nutrition_basis") else None,
        review_status=str(item["review_status"]),
        reviewed_by=str(item["reviewed_by"]) if item.get("reviewed_by") else None,
        reviewed_at=datetime.fromisoformat(str(reviewed_at_raw)) if reviewed_at_raw else None,
        review_notes=str(item["review_notes"]) if item.get("review_notes") else None,
        anchor_food=str(item["anchor_food"]) if item.get("anchor_food") else None,
        continuity_score=int(str(item["continuity_score"])) if item.get("continuity_score") is not None else None,
        is_active=bool(item["is_active"]),
        catalog_version=int(str(item["catalog_version"])),
        taxonomy_version=int(str(item["taxonomy_version"])),
        forbidden_tags_json=_as_string_list(item.get("forbidden_tags", []), field="forbidden_tags"),
        energy_kcal_min_per_person=int(str(item["energy_kcal_min_per_person"])),
        energy_kcal_max_per_person=int(str(item["energy_kcal_max_per_person"])),
        nutrition_note=str(item["nutrition_note"]) if item.get("nutrition_note") else None,
        order_tips_json=_as_string_list(item.get("order_tips", []), field="order_tips"),
        high_protein=bool(item.get("high_protein", False)),
    )


def _apply(target: ExternalDiningCandidate, source: ExternalDiningCandidate) -> None:
    for name in type(source).model_fields:
        if name not in {"id", "created_at"}:
            setattr(target, name, getattr(source, name))
    target.updated_at = datetime.utcnow()


def _insert_cloudbase_candidate(
    session: CloudBaseRepository,
    record: ExternalDiningCandidate,
) -> ExternalDiningCandidate:
    """Recover a committed REST insert when the gateway omits its body."""
    try:
        return session.insert(record)
    except RuntimeError as error:
        if "no representation" not in str(error):
            raise
        recovered = session.first(
            ExternalDiningCandidate,
            filters=(RdbFilter("catalog_key", "eq", record.catalog_key),),
        )
        if recovered is None:
            raise RuntimeError(
                "CloudBase REST candidate insert returned no representation and row was not found",
            ) from error
        return recovered


def _update_cloudbase_candidate(
    session: CloudBaseRepository,
    record: ExternalDiningCandidate,
    *,
    filters: tuple[RdbFilter, ...],
) -> ExternalDiningCandidate:
    """Recover a committed REST update when the gateway omits its body."""
    try:
        return session.update(record, filters=filters)
    except RuntimeError as error:
        if "no representation" not in str(error):
            raise
        recovered = session.first(ExternalDiningCandidate, filters=filters)
        if recovered is None:
            raise RuntimeError(
                "CloudBase REST candidate update returned no representation and row was not found",
            ) from error
        return recovered


def import_seed(
    session: DatabaseSession,
    json_path: Path | str = DEFAULT_SEED_PATH,
    *,
    include_drafts: bool = False,
) -> int:
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"外食候选 seed 不存在: {path}")
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise ValueError("外食候选 seed 顶层必须是 object list")
    records = [_build(cast(dict[str, object], item)) for item in raw]
    if not include_drafts:
        records = [row for row in records if row.review_status == "approved" and row.is_active]

    existing = {row.catalog_key: row for row in _rows(session)}
    for record in records:
        current = existing.get(record.catalog_key)
        if current is None:
            if is_cloudbase_repository(session):
                current = _insert_cloudbase_candidate(session, record)
            else:
                session.add(record)
                current = record
            existing[record.catalog_key] = current
            continue
        _apply(current, record)
        if is_cloudbase_repository(session):
            if current.id is None:
                raise RuntimeError("CloudBase candidate row is missing id")
            current = _update_cloudbase_candidate(
                session,
                current,
                filters=(RdbFilter("id", "eq", current.id),),
            )
    if isinstance(session, Session):
        session.commit()
    return len(records)
