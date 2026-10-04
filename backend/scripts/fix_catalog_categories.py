"""修正 catalog 中被误写成英文令牌的 category（数据修正脚本）。

背景：批量导入时部分行 category 被填成 meal_family 令牌（如 soup_meal、
single_dish），前端直接展示。本脚本按 external_dining.CATEGORY_BY_FAMILY_SUB
受控词表把这类行的 category 修正为中文分类；已是中文分类的行不动。

用法（在 backend/ 目录下，需 CLOUDBASE_ENV_ID + CLOUDBASE_APIKEY 环境变量）：
    python scripts/fix_catalog_categories.py            # 干跑，只打印计划
    python scripts/fix_catalog_categories.py --apply    # 实际 UPDATE

词表单一来源：app/services/external_dining.py 的 CATEGORY_BY_FAMILY_SUB
（引擎兜底与数据修正共用，避免两边漂移）。
"""

from __future__ import annotations

import argparse
import sys

from app.core.config import get_settings
from app.repositories.cloudbase_rdb import CloudBaseRdbClient, RdbFilter
from app.services.external_dining import CATEGORY_BY_FAMILY_SUB

TABLE = "external_dining_candidates"


def fetch_rows(client: CloudBaseRdbClient) -> list[dict]:
    result = client.select(
        TABLE,
        columns=("id", "dish_name", "category", "meal_family", "sub_family"),
        filters=(
            RdbFilter("review_status", "eq", "approved"),
            RdbFilter("is_active", "is", True),
        ),
        limit=1000,
    )
    return list(result.rows)


def plan_fixes(rows: list[dict]) -> list[tuple[dict, str]]:
    fixes: list[tuple[dict, str]] = []
    for row in rows:
        category = str(row.get("category") or "")
        key = (str(row.get("meal_family") or ""), str(row.get("sub_family") or ""))
        mapped = CATEGORY_BY_FAMILY_SUB.get(key)
        if mapped is not None and (category != mapped) and category.isascii():
            fixes.append((row, mapped))
    return fixes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际执行 UPDATE（默认干跑只打印计划）",
    )
    args = parser.parse_args()

    settings = get_settings()
    api_key = settings.cloudbase_server_api_key
    if api_key is None:
        print("缺少 CLOUDBASE_APIKEY / CLOUDBASE_DB_API_KEY，无法连接生产库", file=sys.stderr)
        return 2
    if not settings.cloudbase_env_id:
        print("缺少 CLOUDBASE_ENV_ID", file=sys.stderr)
        return 2

    client = CloudBaseRdbClient(
        env_id=settings.cloudbase_env_id,
        api_key=api_key,
        timeout_seconds=settings.cloudbase_db_timeout_seconds,
        read_retries=settings.cloudbase_db_read_retries,
    )
    try:
        fixes = plan_fixes(fetch_rows(client))
    finally:
        client.close()

    if not fixes:
        print("没有需要修正的行")
        return 0

    for row, mapped in fixes:
        print(f"#{row['id']} {row['dish_name']}: {row['category']} -> {mapped}")

    if not args.apply:
        print(f"\n干跑完成：{len(fixes)} 行待修正（加 --apply 实际执行）")
        return 0

    updated = 0
    for row, mapped in fixes:
        client = CloudBaseRdbClient(
            env_id=settings.cloudbase_env_id,
            api_key=api_key,
            timeout_seconds=settings.cloudbase_db_timeout_seconds,
            read_retries=settings.cloudbase_db_read_retries,
        )
        try:
            result = client.update(
                TABLE,
                values={"category": mapped},
                filters=(RdbFilter("id", "eq", row["id"]),),
            )
            affected = result.affected if result.affected is not None else 1
            updated += affected
            print(f"#{row['id']} updated, affected={affected}")
        finally:
            client.close()
    print(f"\n完成：{updated}/{len(fixes)} 行已修正")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
