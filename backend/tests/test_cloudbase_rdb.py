"""CloudBase MySQL HTTPS REST client contract tests."""

import httpx
import pytest

from app.repositories.cloudbase_rdb import (
    CloudBaseRdbClient,
    CloudBaseRdbError,
    RdbFilter,
    RdbOrder,
)

ENV_ID = "cloud1-test"
API_KEY = "server-only-api-key"


def _client(
    handler: httpx.MockTransport,
    *,
    read_retries: int = 1,
) -> CloudBaseRdbClient:
    return CloudBaseRdbClient(
        env_id=ENV_ID,
        api_key=API_KEY,
        timeout_seconds=1,
        read_retries=read_retries,
        transport=handler,
    )


def test_select_encodes_filters_order_and_count_without_leaking_key() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            headers={"Content-Range": "0-1/2", "X-Request-Id": "req-read"},
            json=[{"id": 7}, {"id": 8}],
        )

    client = _client(httpx.MockTransport(handler))
    try:
        result = client.select(
            "dining_memories",
            columns=("id", "dish_name"),
            filters=(RdbFilter("user_id", "eq", 7),),
            order=(RdbOrder("updated_at", "desc"),),
            limit=2,
            offset=0,
            count=True,
        )
    finally:
        client.close()

    request = captured[0]
    assert request.url.path == "/v1/rdb/rest/dining_memories"
    assert request.url.params["select"] == "id,dish_name"
    assert request.url.params["user_id"] == "eq.7"
    assert request.url.params["order"] == "updated_at.desc"
    assert request.url.params["limit"] == "2"
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert request.headers["Prefer"] == "count=exact"
    assert result.rows == [{"id": 7}, {"id": 8}]
    assert result.total == 2
    assert result.request_id == "req-read"
    assert API_KEY not in repr(client)


def test_in_filter_encodes_a_bounded_scalar_list() -> None:
    assert RdbFilter("id", "in", [7, 8]).as_query_value() == "in.(7,8)"


def test_upsert_uses_unique_conflict_semantics_and_returns_rows() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            201,
            headers={"Content-Range": "*/2"},
            json=[{"user_id": 7, "birthday": "2000-01-01"}],
        )

    client = _client(httpx.MockTransport(handler))
    try:
        result = client.upsert(
            "user_profiles",
            {"user_id": 7, "birthday": "2000-01-01"},
        )
    finally:
        client.close()

    request = captured[0]
    assert request.method == "POST"
    assert request.headers["Prefer"] == "return=representation, resolution=merge-duplicates"
    assert result.rows == [{"user_id": 7, "birthday": "2000-01-01"}]
    assert result.affected == 2


@pytest.mark.parametrize("method_name", ["update", "delete"])
def test_mutations_require_a_filter(method_name: str) -> None:
    client = _client(
        httpx.MockTransport(lambda _: httpx.Response(500)),
    )
    try:
        method = getattr(client, method_name)
        with pytest.raises(ValueError, match="filter"):
            if method_name == "update":
                method("users", {"nickname": "unsafe"}, filters=())
            else:
                method("users", filters=())
    finally:
        client.close()


def test_get_retries_once_on_503() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"code": "OPERATION_FAILED", "message": "busy"})
        return httpx.Response(200, json=[{"id": 1}])

    client = _client(httpx.MockTransport(handler))
    try:
        result = client.select("foods")
    finally:
        client.close()

    assert calls == 2
    assert result.rows == [{"id": 1}]


def test_non_idempotent_write_is_not_retried() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            503,
            headers={"X-Request-Id": "req-write"},
            json={"code": "OPERATION_FAILED", "message": "busy"},
        )

    client = _client(httpx.MockTransport(handler))
    try:
        with pytest.raises(CloudBaseRdbError) as captured:
            client.insert("recommendation_events", {"user_id": 7})
    finally:
        client.close()

    assert calls == 1
    assert captured.value.code == "OPERATION_FAILED"
    assert captured.value.request_id == "req-write"
    assert API_KEY not in str(captured.value)


def test_error_envelope_is_normalized_without_response_body_dump() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"X-Request-Id": "req-denied"},
            json={
                "code": "PERMISSION_DENIED",
                "message": "forbidden",
                "debug": API_KEY,
            },
        )

    client = _client(httpx.MockTransport(handler), read_retries=0)
    try:
        with pytest.raises(CloudBaseRdbError) as captured:
            client.select("users")
    finally:
        client.close()

    error = captured.value
    assert error.status_code == 403
    assert error.code == "PERMISSION_DENIED"
    assert error.request_id == "req-denied"
    assert str(error) == "CloudBase MySQL 请求失败: forbidden"
    assert API_KEY not in repr(error)
