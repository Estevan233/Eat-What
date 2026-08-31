"""Validate external dining seed structure, review state and distribution."""

# Direct source execution needs to prefer this checkout over an installed app.
# The import-order exception is intentionally limited to this bootstrap.
# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import json
from collections import Counter
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.candidate_catalog_validation import CatalogTaxonomy
from app.services.candidate_catalog_validation import (
    load_taxonomy,
    normalize_candidate_name,
    validate_common_candidate,
    weak_variant_fingerprint,
)

DEFAULT_PATH = BACKEND_ROOT / "data" / "external_dining_seed.json"
DEFAULT_TAXONOMY = BACKEND_ROOT / "data" / "candidate_taxonomy_v1.json"


def _validate_row(
    raw: object,
    index: int,
    taxonomy: CatalogTaxonomy,
    keys: set[str],
    names: set[str],
    weak_names: dict[str, str],
) -> tuple[list[str], dict[str, object] | None]:
    if not isinstance(raw, dict):
        return [f"[#{index}] 必须是 object"], None
    key = raw.get("catalog_key")
    prefix = f"[#{index} {key or '-'}]"
    errors = [
        f"{prefix} {issue.field}: {issue.message}"
        for issue in validate_common_candidate(raw, taxonomy, kind="external")
    ]
    if isinstance(key, str):
        if key in keys:
            errors.append(f"{prefix} catalog_key 重复")
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
    energy_min = raw.get("energy_kcal_min_per_person")
    energy_max = raw.get("energy_kcal_max_per_person")
    if not isinstance(energy_min, int) or not isinstance(energy_max, int):
        errors.append(f"{prefix} 能量范围必须为整数")
    elif not 0 <= energy_min <= energy_max <= 1500:
        errors.append(f"{prefix} 能量范围非法")
    approved = raw if raw.get("review_status") == "approved" and raw.get("is_active") is True else None
    return errors, approved


def _validate_distribution(approved: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    if not 300 <= len(approved) <= 320:
        errors.append(f"approved 外食候选必须为 300-320，实际 {len(approved)}")
    styles = Counter(str(row.get("serving_style")) for row in approved)
    families = Counter(str(row.get("meal_family")) for row in approved)
    delivery = Counter(str(row.get("delivery_fit")) for row in approved)
    if styles["individual"] < 180:
        errors.append(f"individual 至少 180，实际 {styles['individual']}")
    if styles["shared"] < 90:
        errors.append(f"shared 至少 90，实际 {styles['shared']}")
    if len(families) < 10:
        errors.append(f"meal_family 至少 10 类，实际 {len(families)}")
    if approved and max(families.values(), default=0) / len(approved) > 0.2:
        errors.append("单一 meal_family 超过 20%")
    if approved and (delivery["high"] + delivery["medium"]) / len(approved) < 0.7:
        errors.append("delivery_fit high|medium 低于 70%")
    return errors


def validate(rows: object, *, allow_draft: bool) -> list[str]:
    if not isinstance(rows, list):
        return ["顶层必须是 list"]
    taxonomy = load_taxonomy(DEFAULT_TAXONOMY)
    errors: list[str] = []
    keys: set[str] = set()
    names: set[str] = set()
    weak_names: dict[str, str] = {}
    approved: list[dict[str, object]] = []
    for index, raw in enumerate(rows):
        row_errors, approved_row = _validate_row(
            raw,
            index,
            taxonomy,
            keys,
            names,
            weak_names,
        )
        errors.extend(row_errors)
        if approved_row is not None:
            approved.append(approved_row)
    if allow_draft:
        return errors
    errors.extend(_validate_distribution(approved))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--allow-draft", action="store_true")
    args = parser.parse_args()
    rows: object = json.loads(args.path.read_text(encoding="utf-8"))
    errors = validate(rows, allow_draft=args.allow_draft)
    if errors:
        print(f"[FAIL] {len(errors)} 个错误")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"[OK] 外食候选目录通过校验: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
