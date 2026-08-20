"""Read-only smoke test for CloudBase MySQL HTTPS REST.

Run inside the CloudRun container after enabling CloudBase API Key injection.
The script deliberately prints neither the key nor response rows.
"""

from app.core.config import get_settings
from app.repositories.cloudbase_rdb import CloudBaseRdbClient


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
        result = client.select(
            "foods",
            columns=("id", "name"),
            limit=1,
            count=True,
        )
    finally:
        client.close()

    print(
        "cloudbase_rdb_read_ok",
        f"status={result.status_code}",
        f"rows={len(result.rows)}",
        f"total={result.total}",
        f"request_id={result.request_id or '-'}",
    )


if __name__ == "__main__":
    main()
