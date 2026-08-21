from typing import Any

from app.repositories.cloudbase_rdb import RdbFilter, RdbResult
from scripts.verify_cloudbase_rdb import verify_write_contract


class WriteProbeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any], tuple[RdbFilter, ...]]] = []

    def insert(self, table: str, values: dict[str, Any]) -> RdbResult:
        self.calls.append(("insert", table, values, ()))
        return RdbResult(
            rows=[{"id": 42, **values}],
            status_code=201,
            request_id="insert-request",
            affected=1,
        )

    def update(
        self,
        table: str,
        values: dict[str, Any],
        *,
        filters: tuple[RdbFilter, ...],
    ) -> RdbResult:
        self.calls.append(("update", table, values, filters))
        return RdbResult(
            rows=[{"id": 42, "openid": "diagnostic", **values}],
            status_code=200,
            request_id="update-request",
            affected=1,
        )

    def delete(
        self,
        table: str,
        *,
        filters: tuple[RdbFilter, ...],
    ) -> RdbResult:
        self.calls.append(("delete", table, {}, filters))
        return RdbResult(
            rows=[{"id": 42}],
            status_code=200,
            request_id="delete-request",
            affected=1,
        )


def test_write_contract_uses_insert_update_delete_and_cleans_up() -> None:
    client = WriteProbeClient()

    summary = verify_write_contract(client)  # type: ignore[arg-type]

    assert [call[0] for call in client.calls] == ["insert", "update", "delete"]
    assert all(call[1] == "users" for call in client.calls)
    assert client.calls[0][2]["openid"].startswith("diagnostic:")
    assert "id" not in client.calls[1][2]
    assert client.calls[1][3] == (RdbFilter("id", "eq", 42),)
    assert client.calls[2][3] == (RdbFilter("id", "eq", 42),)
    assert summary == {
        "insert_status": 201,
        "update_status": 200,
        "delete_status": 200,
        "insert_request_id": "insert-request",
        "update_request_id": "update-request",
        "delete_request_id": "delete-request",
    }
