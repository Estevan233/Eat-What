"""Small, strict client for CloudBase MySQL's HTTPS REST API.

The client deliberately exposes table operations instead of arbitrary SQL.
It keeps the server API Key private, rejects unfiltered mutations, retries
reads only, and normalizes CloudBase error envelopes without dumping bodies.
"""

from __future__ import annotations

import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal, cast

import httpx
from pydantic import SecretStr

FilterOperator = Literal["eq", "neq", "gt", "gte", "lt", "lte", "like", "in", "is"]
OrderDirection = Literal["asc", "desc"]
Scalar = str | int | float | bool | date | datetime | None
QueryParam = tuple[str, str | int | float | bool | None]

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _require_identifier(value: str, *, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value


def _format_scalar(value: Scalar) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date | datetime):
        return value.isoformat()
    return str(value)


def _format_in_value(value: Scalar) -> str:
    raw = _format_scalar(value)
    if isinstance(value, str) and any(char in raw for char in (",", "(", ")", '"', chr(92))):
        escaped = raw.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return raw


@dataclass(frozen=True)
class RdbFilter:
    field: str
    operator: FilterOperator
    value: Scalar | Sequence[Scalar]

    def as_query_value(self) -> str:
        _require_identifier(self.field, label="filter field")
        if self.operator == "in":
            if isinstance(self.value, str | bytes) or not isinstance(self.value, Sequence):
                raise ValueError("in filter requires a sequence")
            items = self.value
            return f"in.({','.join(_format_in_value(item) for item in items)})"
        if isinstance(self.value, Sequence) and not isinstance(self.value, str | bytes):
            raise ValueError("only in filter accepts a sequence")
        return f"{self.operator}.{_format_scalar(cast(Scalar, self.value))}"


@dataclass(frozen=True)
class RdbOrder:
    field: str
    direction: OrderDirection = "asc"

    def as_query_value(self) -> str:
        return f"{_require_identifier(self.field, label='order field')}.{self.direction}"


@dataclass(frozen=True)
class RdbResult:
    rows: list[dict[str, Any]]
    status_code: int
    request_id: str | None = None
    total: int | None = None
    affected: int | None = None


class CloudBaseRdbError(RuntimeError):
    """Sanitized CloudBase MySQL failure safe for logs and API translation."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        request_id: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        safe_message = " ".join(message.split())[:300] or "unknown error"
        super().__init__(f"CloudBase MySQL 请求失败: {safe_message}")


class CloudBaseRdbClient:
    """Synchronous REST client used by FastAPI's synchronous service layer."""

    def __init__(
        self,
        *,
        env_id: str,
        api_key: SecretStr | str,
        timeout_seconds: float = 5.0,
        read_retries: int = 1,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not env_id:
            raise ValueError("env_id is required")
        secret = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        if not secret:
            raise ValueError("api_key is required")
        if read_retries < 0:
            raise ValueError("read_retries must be non-negative")
        self._read_retries = read_retries
        self._client = httpx.Client(
            base_url=f"https://{env_id}.api.tcloudbasegateway.com",
            headers={
                "Authorization": f"Bearer {secret}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
            transport=transport,
        )

    def __repr__(self) -> str:
        return f"{type(self).__name__}(configured=True)"

    def close(self) -> None:
        self._client.close()

    def select(
        self,
        table: str,
        *,
        columns: Sequence[str] = ("*",),
        filters: Sequence[RdbFilter] = (),
        order: Sequence[RdbOrder] = (),
        limit: int | None = None,
        offset: int | None = None,
        count: bool = False,
    ) -> RdbResult:
        params = self._query_params(
            columns=columns,
            filters=filters,
            order=order,
            limit=limit,
            offset=offset,
        )
        headers = {"Prefer": "count=exact"} if count else None
        return self._request(
            "GET",
            self._table_path(table),
            params=params,
            headers=headers,
            retryable=True,
        )

    def insert(
        self,
        table: str,
        values: dict[str, Any] | Sequence[dict[str, Any]],
    ) -> RdbResult:
        return self._write("POST", table, values=values)

    def upsert(
        self,
        table: str,
        values: dict[str, Any] | Sequence[dict[str, Any]],
    ) -> RdbResult:
        return self._write(
            "POST",
            table,
            values=values,
            prefer="return=representation, resolution=merge-duplicates",
        )

    def update(
        self,
        table: str,
        values: dict[str, Any],
        *,
        filters: Sequence[RdbFilter],
    ) -> RdbResult:
        if not filters:
            raise ValueError("update requires at least one filter")
        return self._write("PATCH", table, values=values, filters=filters)

    def delete(
        self,
        table: str,
        *,
        filters: Sequence[RdbFilter],
    ) -> RdbResult:
        if not filters:
            raise ValueError("delete requires at least one filter")
        params: list[QueryParam] = [("select", "*")]
        params.extend((item.field, item.as_query_value()) for item in filters)
        return self._request(
            "DELETE",
            self._table_path(table),
            params=params,
            headers={"Prefer": "return=representation"},
            retryable=False,
        )

    def _write(
        self,
        method: Literal["POST", "PATCH"],
        table: str,
        *,
        values: dict[str, Any] | Sequence[dict[str, Any]],
        filters: Sequence[RdbFilter] = (),
        prefer: str = "return=representation",
    ) -> RdbResult:
        params: list[QueryParam] = [("select", "*")]
        params.extend((item.field, item.as_query_value()) for item in filters)
        return self._request(
            method,
            self._table_path(table),
            params=params,
            headers={"Prefer": prefer},
            json=values,
            retryable=False,
        )

    @staticmethod
    def _table_path(table: str) -> str:
        return f"/v1/rdb/rest/{_require_identifier(table, label='table')}"

    @staticmethod
    def _query_params(
        *,
        columns: Sequence[str],
        filters: Sequence[RdbFilter],
        order: Sequence[RdbOrder],
        limit: int | None,
        offset: int | None,
    ) -> list[QueryParam]:
        if not columns:
            raise ValueError("at least one column is required")
        for column in columns:
            if column != "*":
                _require_identifier(column, label="column")
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative")
        if offset is not None and offset < 0:
            raise ValueError("offset must be non-negative")
        params: list[QueryParam] = [("select", ",".join(columns))]
        params.extend((item.field, item.as_query_value()) for item in filters)
        if order:
            params.append(("order", ",".join(item.as_query_value() for item in order)))
        if limit is not None:
            params.append(("limit", str(limit)))
        if offset is not None:
            params.append(("offset", str(offset)))
        return params

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: list[QueryParam] | None = None,
        headers: dict[str, str] | None = None,
        json: Any = None,
        retryable: bool,
    ) -> RdbResult:
        attempts = self._read_retries + 1 if retryable else 1
        for attempt in range(attempts):
            try:
                query_params = httpx.QueryParams(params) if params is not None else None
                response = self._client.request(
                    method,
                    path,
                    params=query_params,
                    headers=headers,
                    json=json,
                )
            except httpx.TransportError as exc:
                if attempt + 1 < attempts:
                    time.sleep(0.05 * (attempt + 1))
                    continue
                raise CloudBaseRdbError(
                    status_code=503,
                    code="NETWORK_ERROR",
                    message="network error",
                ) from exc
            if response.status_code < 400:
                return self._result(response)
            if retryable and response.status_code == 503 and attempt + 1 < attempts:
                time.sleep(0.05 * (attempt + 1))
                continue
            raise self._error(response)
        raise AssertionError("unreachable")

    @classmethod
    def _result(cls, response: httpx.Response) -> RdbResult:
        payload: Any = response.json() if response.content else []
        if isinstance(payload, dict):
            rows = [payload]
        elif isinstance(payload, list) and all(isinstance(row, dict) for row in payload):
            rows = payload
        else:
            raise CloudBaseRdbError(
                status_code=502,
                code="INVALID_RESPONSE",
                message="unexpected response shape",
                request_id=cls._request_id(response),
            )
        content_range = response.headers.get("Content-Range")
        total, affected = cls._parse_content_range(content_range)
        return RdbResult(
            rows=rows,
            status_code=response.status_code,
            request_id=cls._request_id(response),
            total=total,
            affected=affected,
        )

    @classmethod
    def _error(cls, response: httpx.Response) -> CloudBaseRdbError:
        code = "HTTP_ERROR"
        message = response.reason_phrase or "request failed"
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            raw_code = payload.get("code")
            raw_message = payload.get("message")
            if isinstance(raw_code, str) and raw_code:
                code = raw_code
            if isinstance(raw_message, str) and raw_message:
                message = raw_message
        return CloudBaseRdbError(
            status_code=response.status_code,
            code=code,
            message=message,
            request_id=cls._request_id(response),
        )

    @staticmethod
    def _request_id(response: httpx.Response) -> str | None:
        return cast(
            str | None,
            response.headers.get("X-Request-Id")
            or response.headers.get("X-CloudBase-Request-Id")
            or response.headers.get("Request-Id"),
        )

    @staticmethod
    def _parse_content_range(value: str | None) -> tuple[int | None, int | None]:
        if not value or "/" not in value:
            return None, None
        prefix, raw_count = value.rsplit("/", 1)
        if not raw_count.isdigit():
            return None, None
        count = int(raw_count)
        if "-" in prefix and prefix[:1].isdigit():
            return count, None
        return None, count
