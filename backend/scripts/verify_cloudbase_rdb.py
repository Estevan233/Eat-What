"""Read-only contract test for CloudBase MySQL HTTPS REST.

Run inside the CloudRun container after enabling CloudBase API Key injection.
The script deliberately prints neither the key nor response rows.
"""

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


def main() -> None:
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
    finally:
        client.close()

    print(
        "cloudbase_rdb_read_ok",
        f"status={summary['status']}",
        f"rows={summary['page_rows']}",
        f"total={summary['total']}",
        f"request_id={summary['request_id']}",
    )


if __name__ == "__main__":
    main()
