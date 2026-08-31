"""Build the immutable 205/120/57 candidate-catalog baseline manifest."""

# Direct source execution needs to prefer this checkout over an installed app.
# The import-order exception is intentionally limited to this bootstrap.
# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.external_dining import RULE_CANDIDATES
FOOD_PATH = BACKEND_ROOT / "data" / "food_seed.json"
RECIPE_PATH = BACKEND_ROOT / "data" / "recipe_seed.json"
DEFAULT_OUTPUT = BACKEND_ROOT / "data" / "candidate_catalog_baseline.json"
CLAIM_TERMS = (
    "清热", "解毒", "祛湿", "润肺", "补气", "养胃", "滋阴", "健脾",
    "补血", "安神", "降火", "利尿", "活血", "温补", "驱寒",
)


def _load_list(path: Path) -> list[dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise ValueError(f"{path} must contain a list of objects")
    return raw


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy_rule_key(category: str, dish_name: str) -> str:
    digest = hashlib.sha1(f"{category}:{dish_name}".encode()).hexdigest()[:10]
    return f"rule-{digest}"


def build_baseline() -> dict[str, object]:
    foods = _load_list(FOOD_PATH)
    recipes = _load_list(RECIPE_PATH)
    food_names = [str(item["name"]) for item in foods]
    recipe_names = [str(item["food_name"]) for item in recipes]
    role_counts = Counter(str(item["meal_role"]) for item in recipes)
    claim_matches: list[dict[str, object]] = []
    for item in foods:
        description = str(item.get("description") or "")
        matched = [term for term in CLAIM_TERMS if term in description]
        if matched:
            claim_matches.append({"name": str(item["name"]), "terms": matched})

    external_rules = [
        {
            "legacy_key": _legacy_rule_key(candidate.category, candidate.dish_name),
            "dish_name": candidate.dish_name,
            "category": candidate.category,
            "meal_format": candidate.meal_format,
            "serving_style": candidate.serving_style,
        }
        for candidate in RULE_CANDIDATES
    ]
    return {
        "schema_version": 1,
        "food_seed_sha256": _sha256(FOOD_PATH),
        "recipe_seed_sha256": _sha256(RECIPE_PATH),
        "food_count": len(food_names),
        "food_names": food_names,
        "recipe_count": len(recipe_names),
        "recipe_names": recipe_names,
        "recipe_role_counts": dict(sorted(role_counts.items())),
        "external_rule_count": len(external_rules),
        "external_rules": external_rules,
        "claim_review_count": len(claim_matches),
        "claim_review_items": claim_matches,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    baseline = build_baseline()
    args.output.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "candidate_baseline_ok "
        f"foods={baseline['food_count']} "
        f"recipes={baseline['recipe_count']} "
        f"external={baseline['external_rule_count']} "
        f"claims={baseline['claim_review_count']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
