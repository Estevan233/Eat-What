"""Validate the two candidate catalogs and emit an auditable quality summary."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.candidate_catalog_validation import (  # noqa: E402
    load_taxonomy,
    normalize_candidate_name,
    structural_fingerprint,
    validate_common_candidate,
    weak_variant_fingerprint,
)

DEFAULT_FOOD_PATH = BACKEND_ROOT / "data" / "food_seed.json"
DEFAULT_EXTERNAL_PATH = BACKEND_ROOT / "data" / "external_dining_seed.json"
DEFAULT_TAXONOMY_PATH = BACKEND_ROOT / "data" / "candidate_taxonomy_v1.json"


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _cross_catalog_report(
    food_rows: object,
    external_rows: object,
) -> tuple[list[str], dict[str, object]]:
    """Detect hard/weak overlap across live home and approved external rows."""
    food_names = {
        normalize_candidate_name(str(row.get("name")))
        for row in food_rows
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    external_candidates = [
        row
        for row in external_rows
        if isinstance(row, dict)
        and row.get("review_status") == "approved"
        and row.get("is_active") is True
    ]
    exact_overlap = sorted(
        normalized
        for normalized in food_names
        if any(
            normalized == normalize_candidate_name(str(row.get("dish_name")))
            for row in external_candidates
            if isinstance(row.get("dish_name"), str)
        )
    )
    weak_names: dict[str, str] = {}
    structural_names: dict[str, str] = {}
    structural_pairs: list[str] = []
    weak_pairs: list[str] = []
    for kind, row in [
        *[("home", row) for row in food_rows if isinstance(row, dict)],
        *[("external", row) for row in external_candidates],
    ]:
        raw_name = row.get("name") or row.get("dish_name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            continue
        fingerprint = weak_variant_fingerprint(raw_name)
        previous = weak_names.get(fingerprint)
        if previous is not None and previous != raw_name:
            weak_pairs.append(f"{previous} / {raw_name}")
        weak_names[fingerprint] = raw_name
        structural = structural_fingerprint(row, kind=kind)
        if structural is not None:
            previous_structural = structural_names.get(structural)
            if previous_structural is not None and previous_structural != raw_name:
                structural_pairs.append(f"{previous_structural} / {raw_name}")
            structural_names[structural] = raw_name

    errors = [
        f"跨目录 approved 硬重名: {name}"
        for name in exact_overlap
    ]
    return errors, {
        "exact_name_overlap": exact_overlap,
        "weak_variant_pairs": sorted(set(weak_pairs)),
        "structural_duplicate_pairs": sorted(set(structural_pairs)),
    }


def _validate_external(  # noqa: C901
    rows: object,
    taxonomy: object,
    *,
    allow_draft: bool,
) -> tuple[list[str], dict[str, object]]:
    if not isinstance(rows, list):
        return ["external seed 顶层必须是 list"], {}
    errors: list[str] = []
    keys: set[str] = set()
    names: set[str] = set()
    weak_names: dict[str, str] = {}
    structural_names: dict[str, str] = {}
    structural_pairs: list[str] = []
    approved: list[dict[str, object]] = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            errors.append(f"external[#{index}] 必须是 object")
            continue
        key = raw.get("catalog_key")
        prefix = f"external[#{index} {key or '-'}]"
        errors.extend(
            f"{prefix} {issue.field}: {issue.message}"
            for issue in validate_common_candidate(raw, taxonomy, kind="external")
        )
        if isinstance(key, str) and key in keys:
            errors.append(f"{prefix} catalog_key 重复")
        if isinstance(key, str):
            keys.add(key)
        name = raw.get("dish_name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{prefix} dish_name 缺失")
        else:
            normalized = normalize_candidate_name(name)
            if normalized in names:
                errors.append(f"{prefix} 标准化名称重复")
            names.add(normalized)
            weak = weak_variant_fingerprint(name)
            previous = weak_names.get(weak)
            if previous is not None and previous != name:
                errors.append(f"{prefix} 弱变体待审: {previous} / {name}")
            weak_names[weak] = name
        structural = structural_fingerprint(raw, kind="external")
        if structural is not None:
            previous_structural = structural_names.get(structural)
            if previous_structural is not None and previous_structural != name:
                structural_pairs.append(f"{previous_structural} / {name}")
            structural_names[structural] = name
        energy_min = raw.get("energy_kcal_min_per_person")
        energy_max = raw.get("energy_kcal_max_per_person")
        if not isinstance(energy_min, int) or not isinstance(energy_max, int):
            errors.append(f"{prefix} 能量范围必须为整数")
        elif not 0 <= energy_min <= energy_max <= 1500:
            errors.append(f"{prefix} 能量范围非法")
        if raw.get("review_status") == "approved" and raw.get("is_active") is True:
            approved.append(raw)
    summary: dict[str, object] = {
        "rows": len(rows),
        "approved_active": len(approved),
        "draft": sum(1 for row in rows if isinstance(row, dict) and row.get("review_status") == "draft"),
        "serving_style": dict(Counter(str(row.get("serving_style")) for row in approved)),
        "meal_family": dict(Counter(str(row.get("meal_family")) for row in approved)),
        "structural_duplicate_pairs": sorted(set(structural_pairs)),
    }
    if not allow_draft:
        if not 300 <= len(approved) <= 320:
            errors.append(f"approved 外食候选必须为 300-320，实际 {len(approved)}")
        style_counts = Counter(str(row.get("serving_style")) for row in approved)
        family_counts = Counter(str(row.get("meal_family")) for row in approved)
        delivery_counts = Counter(str(row.get("delivery_fit")) for row in approved)
        if style_counts["individual"] < 180:
            errors.append(f"individual 至少 180，实际 {style_counts['individual']}")
        if style_counts["shared"] < 90:
            errors.append(f"shared 至少 90，实际 {style_counts['shared']}")
        if len(family_counts) < 10:
            errors.append(f"meal_family 至少 10 类，实际 {len(family_counts)}")
        if approved and max(family_counts.values(), default=0) / len(approved) > 0.2:
            errors.append("单一 meal_family 超过 20%")
        if approved and (delivery_counts["high"] + delivery_counts["medium"]) / len(approved) < 0.7:
            errors.append("delivery_fit high|medium 低于 70%")
        if summary["structural_duplicate_pairs"]:
            errors.append("approved 外食候选存在结构重复，必须人工确认 variant")
    return errors, summary


def _validate_food(rows: object) -> tuple[list[str], dict[str, object]]:
    if not isinstance(rows, list):
        return ["food seed 顶层必须是 list"], {}
    names = [str(row.get("name")) for row in rows if isinstance(row, dict)]
    errors: list[str] = []
    if len(rows) < 205 or len(rows) > 250:
        errors.append(f"家庭候选必须为 205-250，实际 {len(rows)}")
    if len(names) != len(set(names)):
        errors.append("家庭候选存在重名")
    return errors, {
        "rows": len(rows),
        "unique_names": len(set(names)),
        "category": dict(Counter(str(row.get("category")) for row in rows if isinstance(row, dict))),
        "cooking_method": dict(Counter(str(row.get("cooking_method")) for row in rows if isinstance(row, dict))),
    }


def validate_catalog(
    *,
    food_path: Path = DEFAULT_FOOD_PATH,
    external_path: Path = DEFAULT_EXTERNAL_PATH,
    allow_draft: bool = False,
) -> tuple[list[str], dict[str, object]]:
    taxonomy = load_taxonomy(DEFAULT_TAXONOMY_PATH)
    food_rows = _load(food_path)
    external_rows = _load(external_path)
    food_errors, food_summary = _validate_food(food_rows)
    external_errors, external_summary = _validate_external(
        external_rows,
        taxonomy,
        allow_draft=allow_draft,
    )
    cross_errors, cross_summary = _cross_catalog_report(food_rows, external_rows)
    catalog_total = int(food_summary.get("rows", 0)) + int(
        external_summary.get("approved_active", 0)
    )
    errors = food_errors + external_errors
    if not allow_draft:
        errors.extend(cross_errors)
        if cross_summary["structural_duplicate_pairs"]:
            errors.append("跨目录存在结构重复，必须人工确认 variant")
        if catalog_total < 500:
            errors.append(f"approved 候选目录总数必须至少 500，实际 {catalog_total}")
    return errors, {
        "food": food_summary,
        "external": external_summary,
        "approved_total": int(external_summary.get("approved_active", 0)),
        "catalog_total": catalog_total,
        "cross_catalog_exact_name_overlap": len(cross_summary["exact_name_overlap"]),
        "cross_catalog": cross_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--food-path", type=Path, default=DEFAULT_FOOD_PATH)
    parser.add_argument("--external-path", type=Path, default=DEFAULT_EXTERNAL_PATH)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--allow-draft", action="store_true")
    args = parser.parse_args()
    errors, summary = validate_catalog(
        food_path=args.food_path,
        external_path=args.external_path,
        allow_draft=args.allow_draft,
    )
    if args.report:
        args.report.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if errors:
        print(f"[FAIL] {len(errors)} 个错误")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(
        "[OK] 候选目录报告 "
        f"foods={summary['food']['rows']} "
        f"external={summary['external']['rows']} "
        f"approved={summary['approved_total']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
