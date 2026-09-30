"""Phase 0 多样性现状测量（只读，一次性分析脚本）。

用法（在 backend/ 目录下）：
    python scripts/measure_dining_diversity.py --days 30

数据源为 CloudBase RDB REST，与 scripts/verify_cloudbase_rdb.py 同一通道：
- 云托管容器内：注入的 CLOUDBASE_APIKEY 直接可用（Webshell 运行）；
- 本地：.env 需配置 CLOUDBASE_ENV_ID + CLOUDBASE_DB_API_KEY。

只输出聚合指标：user_id 经每次运行随机盐哈希，不打印 request_id、openid 或逐行数据。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import uuid
from collections import Counter, defaultdict, deque
from datetime import date, datetime, timedelta
from itertools import pairwise
from typing import Any

from app.core.config import get_settings
from app.repositories.cloudbase_rdb import CloudBaseRdbClient, RdbFilter, RdbOrder
from app.services.external_dining import EXTERNAL_HISTORY_DAYS, RULE_CANDIDATES

PAGE_SIZE = 1000
BATCH_GAP_MINUTES = 30
WINDOW_COLUMN = (
    "user_id",
    "event_date",
    "dining_mode",
    "audience",
    "party_size",
    "engine",
    "primary_meal_json",
    "summary_json",
    "created_at",
)

UserEvents = dict[str, list[dict[str, Any]]]


def _rule_key(category: str, dish_name: str) -> str:
    digest = hashlib.sha1(f"{category}:{dish_name}".encode()).hexdigest()[:10]
    return f"rule-{digest}"


def build_local_key_map() -> dict[str, dict[str, Any]]:
    """本地规则候选的 key → 元信息（external_catalog_enabled 关闭时的 key 形态）。"""
    mapping: dict[str, dict[str, Any]] = {}
    for candidate in RULE_CANDIDATES:
        key = (
            candidate.legacy_key
            or candidate.catalog_key
            or _rule_key(candidate.category, candidate.dish_name)
        )
        mapping[key] = {
            "category": candidate.category,
            "meal_format": candidate.meal_format,
            "serving_style": candidate.serving_style,
            "dish_name": candidate.dish_name,
        }
    return mapping


def fetch_events(
    client: CloudBaseRdbClient, start: date, end: date
) -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    offset = 0
    last_request_id = "-"
    while True:
        page = client.select(
            "recommendation_events",
            columns=WINDOW_COLUMN,
            filters=(
                RdbFilter("event_date", "gte", start),
                RdbFilter("event_date", "lte", end),
            ),
            order=(RdbOrder("created_at", "asc"),),
            limit=PAGE_SIZE,
            offset=offset,
        )
        last_request_id = page.request_id or "-"
        rows.extend(page.rows)
        if len(page.rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows, last_request_id


def fetch_catalog_counts(client: CloudBaseRdbClient) -> dict[str, int]:
    def count(filters: tuple[RdbFilter, ...]) -> int:
        page = client.select(
            "external_dining_candidates",
            columns=("id",),
            filters=filters,
            limit=1,
            count=True,
        )
        return page.total if page.total is not None else len(page.rows)

    return {
        "total": count(()),
        "approved": count((RdbFilter("review_status", "eq", "approved"),)),
        "approved_active": count(
            (
                RdbFilter("review_status", "eq", "approved"),
                RdbFilter("is_active", "eq", True),
            )
        ),
    }


def external_keys(event: dict[str, Any]) -> list[str]:
    payload = event.get("primary_meal_json") or {}
    raw = payload.get("suggestion_keys") if isinstance(payload, dict) else None
    if not raw:
        summary = event.get("summary_json") or {}
        raw = summary.get("suggestion_keys") if isinstance(summary, dict) else None
    if not isinstance(raw, list):
        return []
    return [value for value in raw if isinstance(value, str)]


def meal_formats(event: dict[str, Any]) -> list[str]:
    summary = event.get("summary_json") or {}
    raw = summary.get("meal_formats") if isinstance(summary, dict) else None
    if not isinstance(raw, list):
        return []
    return [value for value in raw if isinstance(value, str)]


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _pct(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _dist(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"median": None, "p90": None, "mean": None}
    ordered = sorted(values)
    p90 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))]
    return {
        "median": round(statistics.median(values), 4),
        "p90": round(p90, 4),
        "mean": round(statistics.fmean(values), 4),
    }


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _exposure_reuse(by_user: UserEvents) -> dict[str, Any]:
    """相对同用户此前 7 天（含当日更早请求）已曝光 key 集的复用程度。

    与线上引擎语义对齐：external_dining.py 的曝光窗口按 event_date
    取 [d-6, d]，同请求之前的当日事件计入。
    """
    reuse_ratios: list[float] = []
    any_reuse = 0
    full_reuse = 0
    with_prior = 0
    for user_events in by_user.values():
        window: deque[tuple[date, set[str]]] = deque()
        for event in user_events:
            keys = external_keys(event)
            day = _parse_date(event.get("event_date"))
            if not keys or day is None:
                continue
            cutoff = day - timedelta(days=EXTERNAL_HISTORY_DAYS - 1)
            while window and window[0][0] < cutoff:
                window.popleft()
            prior = set().union(*(seen for _, seen in window)) if window else set()
            if prior:
                with_prior += 1
                overlap = len(set(keys) & prior)
                reuse_ratios.append(overlap / len(keys))
                any_reuse += bool(overlap)
                full_reuse += overlap == len(keys)
            window.append((day, set(keys)))
    return {
        "basis": f"相对同用户此前 {EXTERNAL_HISTORY_DAYS} 天（含当日更早请求）已曝光 key 集",
        "events_with_prior": with_prior,
        "any_key_reuse_pct": _pct(any_reuse, with_prior),
        "full_batch_reuse_pct": _pct(full_reuse, with_prior),
        "reuse_ratio_distribution": _dist(reuse_ratios),
    }


def _reshuffle_pairs(by_user: UserEvents, key_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """同用户同日相邻两次外食推荐（间隔 ≤30 分钟）的重叠情况。"""
    pair_count = 0
    any_overlap = 0
    category_adjacent = 0
    decodable = 0
    overlap_sum = 0.0
    for user_events in by_user.values():
        for prev, curr in pairwise(user_events):
            if prev.get("event_date") != curr.get("event_date"):
                continue
            prev_time = _parse_time(prev.get("created_at"))
            curr_time = _parse_time(curr.get("created_at"))
            if (
                prev_time is None
                or curr_time is None
                or (curr_time - prev_time) > timedelta(minutes=BATCH_GAP_MINUTES)
            ):
                continue
            prev_keys, curr_keys = external_keys(prev), external_keys(curr)
            if not prev_keys or not curr_keys:
                continue
            pair_count += 1
            overlap = len(set(prev_keys) & set(curr_keys))
            overlap_sum += overlap
            any_overlap += bool(overlap)
            prev_cat = {key_map[k]["category"] for k in prev_keys if k in key_map}
            curr_cat = {key_map[k]["category"] for k in curr_keys if k in key_map}
            if prev_cat and curr_cat:
                decodable += 1
                category_adjacent += bool(prev_cat & curr_cat)
    return {
        "basis": f"同用户同日相邻外食推荐，间隔 ≤{BATCH_GAP_MINUTES} 分钟",
        "pairs": pair_count,
        "any_overlap_pct": _pct(any_overlap, pair_count),
        "no_overlap_pct": _pct(pair_count - any_overlap, pair_count),
        "mean_overlap_keys": round(overlap_sum / pair_count, 2) if pair_count else None,
        "same_category_adjacent_pct": _pct(category_adjacent, decodable),
        "decodable_pairs": decodable,
    }


def _pool_stats(
    external: list[dict[str, Any]], key_map: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """key 构成：本地规则 / 私人记忆 / 其他（catalog 生效信号），及池覆盖。"""
    all_keys = [key for event in external for key in external_keys(event)]
    key_counter = Counter(all_keys)
    decoded_keys = {key for key in key_counter if key in key_map}
    memory_keys = {key for key in key_counter if key.startswith("memory-")}
    other_keys = set(key_counter) - decoded_keys - memory_keys
    serving_styles = Counter(key_map[key]["serving_style"] for key in decoded_keys)
    pool_individual = sum(1 for meta in key_map.values() if meta["serving_style"] == "individual")
    return {
        "local_rule_pool_total": len(key_map),
        "local_rule_pool_individual": pool_individual,
        "local_rule_pool_shared": len(key_map) - pool_individual,
        "observed_local_rule_keys": len(decoded_keys),
        "observed_memory_keys": len(memory_keys),
        "observed_other_keys": len(other_keys),
        "other_key_examples": sorted(other_keys)[:5],
        "observed_local_keys_by_serving_style": dict(serving_styles),
        "key_shape_distribution": {
            "local_rule_sha": sum(
                count for key, count in key_counter.items() if key in decoded_keys
            ),
            "memory": sum(count for key, count in key_counter.items() if key in memory_keys),
            "other_catalog_or_legacy": sum(
                count for key, count in key_counter.items() if key in other_keys
            ),
        },
    }


def _intra_batch_stats(external: list[dict[str, Any]]) -> dict[str, Any]:
    """批内餐型重复率（设计预期恒为 0，用于校验 select_rotating_suggestions）。"""
    format_dup_batches = 0
    batches_with_formats = 0
    for event in external:
        formats = meal_formats(event)
        if len(formats) >= 2:
            batches_with_formats += 1
            format_dup_batches += len(set(formats)) != len(formats)
    return {
        "batches_with_formats": batches_with_formats,
        "meal_format_duplicate_pct": _pct(format_dup_batches, batches_with_formats),
    }


def analyze(
    events: list[dict[str, Any]],
    *,
    start: date,
    end: date,
    salt: str,
    key_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    def uid_hash(user_id: Any) -> str:
        return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:12]

    external = [
        event
        for event in events
        if event.get("dining_mode") == "eat_out"
        and (event.get("primary_meal_json") or {}).get("kind") == "external_dining_v2"
    ]
    by_user: UserEvents = defaultdict(list)
    for event in external:
        if event.get("created_at") is not None:
            by_user[uid_hash(event.get("user_id"))].append(event)
    for user_events in by_user.values():
        user_events.sort(key=lambda item: item["created_at"])

    per_user_counts = [len(user_events) for user_events in by_user.values()]
    events_per_day = Counter(str(event.get("event_date")) for event in external)
    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "overview": {
            "all_events": len(events),
            "external_events": len(external),
            "external_users": len(by_user),
            "events_per_user_median": statistics.median(per_user_counts) if per_user_counts else 0,
            "events_per_user_max": max(per_user_counts) if per_user_counts else 0,
            "external_events_per_day_max": max(events_per_day.values()) if events_per_day else 0,
            "distinct_suggestion_keys": len(
                {key for event in external for key in external_keys(event)}
            ),
            "engine_distribution": dict(Counter(str(event.get("engine")) for event in external)),
        },
        "pool": _pool_stats(external, key_map),
        "exposure_reuse": _exposure_reuse(by_user),
        "reshuffle_pairs": _reshuffle_pairs(by_user, key_map),
        "intra_batch": _intra_batch_stats(external),
    }


def _safe_catalog_counts(
    client: CloudBaseRdbClient,
) -> tuple[dict[str, int | str], str]:
    """候选目录计数失败不阻断主报告（表可能尚未创建）。"""
    try:
        counts: dict[str, int | str] = fetch_catalog_counts(client)
        page = client.select("external_dining_candidates", columns=("id",), limit=1)
        return counts, page.request_id or "-"
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}, "-"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0 dining diversity measurement")
    parser.add_argument("--days", type=int, default=30, help="分析窗口天数（默认 30）")
    args = parser.parse_args()

    settings = get_settings()
    api_key = settings.cloudbase_server_api_key
    if api_key is None or not api_key.get_secret_value():
        raise SystemExit(
            "CloudBase Server API Key 未配置"
            "（容器内应注入 CLOUDBASE_APIKEY；本地需 CLOUDBASE_DB_API_KEY）"
        )
    if not settings.cloudbase_env_id:
        raise SystemExit("CLOUDBASE_ENV_ID 未配置")

    end = date.today()
    start = end - timedelta(days=args.days - 1)
    salt = uuid.uuid4().hex
    key_map = build_local_key_map()

    client = CloudBaseRdbClient(
        env_id=settings.cloudbase_env_id,
        api_key=api_key,
        timeout_seconds=settings.cloudbase_db_timeout_seconds,
        read_retries=settings.cloudbase_db_read_retries,
    )
    try:
        events, events_request_id = fetch_events(client, start, end)
        catalog_counts, catalog_request_id = _safe_catalog_counts(client)
    finally:
        client.close()

    report = analyze(events, start=start, end=end, salt=salt, key_map=key_map)
    report["catalog_table"] = catalog_counts
    report["audit"] = {
        "report_version": "phase0-v1",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "window_days": args.days,
        "rdb_request_ids": {
            "recommendation_events_last_page": events_request_id,
            "catalog_counts": catalog_request_id,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
