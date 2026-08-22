"""Typed model repository backed by CloudBase MySQL HTTPS REST operations."""

from __future__ import annotations

import builtins
import json
from collections.abc import Sequence
from time import monotonic
from typing import Any, TypeAlias, TypeVar, cast

from sqlalchemy import JSON
from sqlmodel import Session, SQLModel
from typing_extensions import TypeIs

from app.repositories.cloudbase_rdb import (
    CloudBaseRdbClient,
    RdbFilter,
    RdbOrder,
)

ModelT = TypeVar("ModelT", bound=SQLModel)


class CloudBaseRepository:
    """Small typed facade; business services still own authorization filters."""

    is_cloudbase_rest = True

    def __init__(self, client: CloudBaseRdbClient) -> None:
        self.client = client
        self._cache: dict[str, tuple[float, Any]] = {}

    def cache_get(self, key: str, *, max_age_seconds: float) -> Any | None:
        cached = self._cache.get(key)
        if cached is None:
            return None
        saved_at, value = cached
        if monotonic() - saved_at > max_age_seconds:
            self._cache.pop(key, None)
            return None
        return value

    def cache_set(self, key: str, value: Any) -> None:
        self._cache[key] = (monotonic(), value)

    def close(self) -> None:
        self.client.close()

    def list(
        self,
        model: type[ModelT],
        *,
        filters: Sequence[RdbFilter] = (),
        order: Sequence[RdbOrder] = (),
        limit: int | None = None,
        offset: int | None = None,
    ) -> builtins.list[ModelT]:
        result = self.client.select(
            self._table(model),
            filters=filters,
            order=order,
            limit=limit,
            offset=offset,
        )
        return [self._model(model, row) for row in result.rows]

    def list_with_total(
        self,
        model: type[ModelT],
        *,
        filters: Sequence[RdbFilter] = (),
        order: Sequence[RdbOrder] = (),
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[builtins.list[ModelT], int]:
        result = self.client.select(
            self._table(model),
            filters=filters,
            order=order,
            limit=limit,
            offset=offset,
            count=True,
        )
        rows = [self._model(model, row) for row in result.rows]
        return rows, result.total if result.total is not None else len(rows)

    def first(
        self,
        model: type[ModelT],
        *,
        filters: Sequence[RdbFilter] = (),
        order: Sequence[RdbOrder] = (),
    ) -> ModelT | None:
        rows = self.list(model, filters=filters, order=order, limit=1)
        return rows[0] if rows else None

    def get(self, model: type[ModelT], identity: Any) -> ModelT | None:
        table = cast(Any, model).__table__
        primary_keys = [column.name for column in table.primary_key.columns]
        if len(primary_keys) != 1:
            raise ValueError("get requires exactly one primary key")
        return self.first(
            model,
            filters=(RdbFilter(primary_keys[0], "eq", identity),),
        )

    def insert(self, record: ModelT) -> ModelT:
        result = self.client.insert(self._table(type(record)), self._values(record))
        return self._written_model(type(record), result.rows)

    def upsert(self, record: ModelT) -> ModelT:
        result = self.client.upsert(self._table(type(record)), self._values(record))
        return self._written_model(type(record), result.rows)

    def update(
        self,
        record: ModelT,
        *,
        filters: Sequence[RdbFilter],
    ) -> ModelT:
        result = self.client.update(
            self._table(type(record)),
            self._values(record, omit_primary_keys=True),
            filters=filters,
        )
        return self._written_model(type(record), result.rows)

    def delete(
        self,
        model: type[ModelT],
        *,
        filters: Sequence[RdbFilter],
    ) -> int:
        result = self.client.delete(self._table(model), filters=filters)
        return result.affected if result.affected is not None else len(result.rows)

    @staticmethod
    def _table(model: type[SQLModel]) -> str:
        table = cast(str | None, getattr(model, "__tablename__", None))
        if not table:
            raise ValueError("model has no table name")
        return table

    @staticmethod
    def _values(
        record: SQLModel,
        *,
        omit_primary_keys: bool = False,
    ) -> dict[str, Any]:
        values = record.model_dump(mode="json")
        table = cast(Any, record).__table__
        primary_keys = {column.name for column in table.primary_key.columns}
        for column in table.columns:
            value = values.get(column.name)
            if isinstance(column.type, JSON) and value is not None:
                # CloudBase MySQL REST expects JSON-column values as JSON
                # strings. Native arrays/objects are rejected on PATCH and
                # empty arrays can otherwise be persisted as null on POST.
                values[column.name] = json.dumps(
                    value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
        for key in list(values):
            if key in primary_keys and (omit_primary_keys or values[key] is None):
                values.pop(key)
        return values

    @classmethod
    def _written_model(
        cls,
        model: type[ModelT],
        rows: builtins.list[dict[str, Any]],
    ) -> ModelT:
        if not rows:
            raise RuntimeError("CloudBase REST write returned no representation")
        return cls._model(model, rows[0])

    @staticmethod
    def _model(model: type[ModelT], raw: dict[str, Any]) -> ModelT:
        row = dict(raw)
        table = cast(Any, model).__table__
        for column in table.columns:
            value = row.get(column.name)
            if isinstance(column.type, JSON) and isinstance(value, str):
                try:
                    row[column.name] = json.loads(value)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        f"invalid JSON returned for {model.__name__}.{column.name}",
                    ) from exc
            if isinstance(column.type, JSON) and row.get(column.name) is None:
                field = model.model_fields.get(column.name)
                default = (
                    field.get_default(call_default_factory=True)
                    if field is not None
                    else None
                )
                if isinstance(default, builtins.list | dict):
                    # CloudBase's REST gateway can return an empty JSON
                    # collection as null on a later GET. Restore the model's
                    # non-null collection default without changing nullable
                    # JSON fields such as constitution_scores.
                    row[column.name] = default
        return model.model_validate(row)


DatabaseSession: TypeAlias = Session | CloudBaseRepository


def is_cloudbase_repository(value: object) -> TypeIs[CloudBaseRepository]:
    return isinstance(value, CloudBaseRepository)
