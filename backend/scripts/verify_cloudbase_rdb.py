"""Read/write contract tests for CloudBase MySQL HTTPS REST.

Run inside the CloudRun container after enabling CloudBase API Key injection.
The default check is read-only. Pass --write to create, update and delete one
randomized diagnostic user. The script prints neither keys nor row data.
"""

import argparse
from datetime import datetime
from uuid import uuid4

from app.core.config import get_settings
from app.repositories.cloudbase_rdb import CloudBaseRdbClient, RdbFilter, RdbOrder


def verify_read_contract(client: CloudBaseRdbClient) -> dict[str, int | str]:
    page = client.select(
        "foods",
        columns=("id", "name"),
        order=(RdbOrder("id", "asc"),),
        limit=2,
        offset=0,
        count=True,
    )
    if not page.rows or page.total is None:
        raise RuntimeError("foods seed is missing or count contract is unavailable")

    ids = [row.get("id") for row in page.rows]
    if not all(isinstance(value, int) for value in ids):
        raise RuntimeError("foods id response contract is invalid")

    exact = client.select(
        "foods",
        columns=("id",),
        filters=(RdbFilter("id", "eq", ids[0]),),
        limit=1,
    )
    members = client.select(
        "foods",
        columns=("id",),
        filters=(RdbFilter("id", "in", ids),),
        order=(RdbOrder("id", "asc"),),
        limit=len(ids),
    )
    if [row.get("id") for row in exact.rows] != [ids[0]]:
        raise RuntimeError("eq filter contract failed")
    if [row.get("id") for row in members.rows] != ids:
        raise RuntimeError("in/order/limit contract failed")

    return {
        "status": page.status_code,
        "page_rows": len(page.rows),
        "total": page.total,
        "request_id": page.request_id or "-",
    }


def verify_write_contract(client: CloudBaseRdbClient) -> dict[str, int | str]:
    now = datetime.utcnow().isoformat()
    openid = f"diagnostic:{uuid4().hex}"
    inserted = client.insert(
        "users",
        {
            "openid": openid,
            "unionid": None,
            "nickname": "CloudBase 写入诊断",
            "avatar_url": None,
            "created_at": now,
            "updated_at": now,
        },
    )
    if len(inserted.rows) != 1:
        raise RuntimeError("users insert response contract is invalid")
    user_id = inserted.rows[0].get("id")
    if not isinstance(user_id, int):
        raise RuntimeError("users insert did not return an integer id")

    deleted = None
    try:
        updated = client.update(
            "users",
            {
                "nickname": "CloudBase 更新诊断",
                "updated_at": datetime.utcnow().isoformat(),
            },
            filters=(RdbFilter("id", "eq", user_id),),
        )
        if len(updated.rows) != 1 or updated.rows[0].get("id") != user_id:
            raise RuntimeError("users update response contract is invalid")
    finally:
        deleted = client.delete(
            "users",
            filters=(RdbFilter("id", "eq", user_id),),
        )

    if len(deleted.rows) != 1 or deleted.rows[0].get("id") != user_id:
        raise RuntimeError("users delete response contract is invalid")

    return {
        "insert_status": inserted.status_code,
        "update_status": updated.status_code,
        "delete_status": deleted.status_code,
        "insert_request_id": inserted.request_id or "-",
        "update_request_id": updated.request_id or "-",
        "delete_request_id": deleted.request_id or "-",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify CloudBase MySQL REST contracts")
    parser.add_argument(
        "--write",
        action="store_true",
        help="also verify users insert/update/delete with automatic cleanup",
    )
    args = parser.parse_args()

    settings = get_settings()
    api_key = settings.cloudbase_server_api_key
    if api_key is None or not api_key.get_secret_value():
        raise SystemExit(
            "CloudBase Server API Key is not configured "
            "(expected injected CLOUDBASE_APIKEY or explicit CLOUDBASE_DB_API_KEY)"
        )

    client = CloudBaseRdbClient(
        env_id=settings.cloudbase_env_id,
        api_key=api_key,
        timeout_seconds=settings.cloudbase_db_timeout_seconds,
        read_retries=settings.cloudbase_db_read_retries,
    )
    try:
        summary = verify_read_contract(client)
        write_summary = verify_write_contract(client) if args.write else None
    finally:
        client.close()

    print(
        "cloudbase_rdb_read_ok",
        "status=" + str(summary["status"]),
        "rows=" + str(summary["page_rows"]),
        "total=" + str(summary["total"]),
        "request_id=" + str(summary["request_id"]),
    )
    if write_summary is not None:
        print(
            "cloudbase_rdb_write_ok",
            "insert_status=" + str(write_summary["insert_status"]),
            "update_status=" + str(write_summary["update_status"]),
            "delete_status=" + str(write_summary["delete_status"]),
            "insert_request_id=" + str(write_summary["insert_request_id"]),
            "update_request_id=" + str(write_summary["update_request_id"]),
            "delete_request_id=" + str(write_summary["delete_request_id"]),
        )


if __name__ == "__main__":
    main()
