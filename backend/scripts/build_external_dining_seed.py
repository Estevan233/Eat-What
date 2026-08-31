"""Convert the 57 legacy rule candidates into an auditable B0 draft seed."""

# Direct source execution needs to prefer this checkout over an installed app.
# The import-order exception is intentionally limited to this bootstrap.
# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.external_dining import RULE_CANDIDATES, RuleCandidate

DEFAULT_OUTPUT = BACKEND_ROOT / "data" / "external_dining_seed.json"
SOURCE_URL = (
    "https://github.com/Estevan233/Eat-What/blob/"
    "b102480f0ec4857a05b7e71647f1bb272d47bb9c/"
    "backend/app/services/external_dining.py"
)
CHECKED_AT = "2026-08-31T00:00:00+08:00"


def _legacy_key(candidate: RuleCandidate) -> str:
    digest = hashlib.sha1(
        f"{candidate.category}:{candidate.dish_name}".encode()
    ).hexdigest()[:10]
    return f"rule-{digest}"


def _shared_family(meal_format: str) -> tuple[str, str]:
    if "hotpot" in meal_format:
        return "hotpot_grill", "hotpot"
    if "grilled" in meal_format:
        return "hotpot_grill", "grilled_share"
    return "shared_dishes", "regional_share"


def _rice_family(meal_format: str) -> tuple[str, str]:
    if "claypot" in meal_format:
        return "rice_meal", "claypot_rice"
    if "braised" in meal_format or "steamed" in meal_format:
        return "rice_meal", "braised_rice"
    if "curry" in meal_format:
        return "rice_meal", "curry_rice"
    return "rice_meal", "rice_bowl"


def _family(candidate: RuleCandidate) -> tuple[str, str]:
    meal_format = candidate.meal_format
    if candidate.serving_style == "shared":
        return _shared_family(meal_format)
    if "wonton" in meal_format:
        return "dumpling_bun", "wonton"
    if "congee" in meal_format:
        return "grain_congee", "congee"
    if "wrap" in meal_format:
        return "wrap_light_meal", "wrap"
    if "salad" in meal_format:
        return "wrap_light_meal", "salad_set"
    if "rice_noodle" in meal_format or "pho" in meal_format:
        return "noodle_meal", "rice_noodle_soup"
    if "noodle" in meal_format:
        return "noodle_meal", "noodle_soup"
    if "rice" in meal_format or meal_format == "bibimbap":
        return _rice_family(meal_format)
    if "soup" in meal_format:
        return "soup_meal", "stew_soup_set"
    return "set_meal", "balanced_plate"


def _staple(candidate: RuleCandidate, family: str) -> str:
    text = f"{candidate.dish_name}:{candidate.meal_format}"
    if family in {"shared_dishes", "hotpot_grill"}:
        return "mixed"
    if "米线" in text or "河粉" in text or "粉" in candidate.meal_format:
        return "rice_noodle"
    if family == "noodle_meal":
        return "wheat_noodle"
    if family == "dumpling_bun":
        return "dumpling_wrapper"
    if family == "grain_congee":
        return "congee"
    if family == "wrap_light_meal":
        return "wheat_bread" if "卷" in text else "corn"
    return "rice"


def _proteins(candidate: RuleCandidate) -> list[str]:
    text = candidate.dish_name
    proteins: list[str] = []
    for marker, protein in (
        ("鸡", "poultry"),
        ("鸭", "poultry"),
        ("牛", "beef"),
        ("羊", "lamb"),
        ("猪", "pork"),
        ("肉", "pork"),
        ("鱼", "fish"),
        ("虾", "crustacean"),
        ("蛋", "egg"),
        ("豆腐", "soy"),
        ("鹰嘴豆", "legume"),
    ):
        if marker in text and protein not in proteins:
            proteins.append(protein)
    return proteins or ["unknown"]


def _meal_periods(family: str) -> list[str]:
    if family in {"grain_congee", "dumpling_bun"}:
        return ["breakfast", "lunch", "dinner"]
    return ["lunch", "dinner"]


def build_seed() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for candidate in RULE_CANDIDATES:
        legacy_key = _legacy_key(candidate)
        family, sub_family = _family(candidate)
        rows.append(
            {
                "catalog_key": f"external:legacy-{legacy_key[5:]}:v1",
                "legacy_key": legacy_key,
                "dish_name": candidate.dish_name,
                "aliases": [],
                "category": candidate.category,
                "meal_family": family,
                "sub_family": sub_family,
                "cuisine_region": "cn_national",
                "staple_type": _staple(candidate, family),
                "protein_types": _proteins(candidate),
                "serving_style": candidate.serving_style,
                "meal_periods": _meal_periods(family),
                "delivery_fit": "medium" if candidate.serving_style == "shared" else "high",
                "price_band": "standard",
                "nature": "unknown",
                "seasonal_solar_terms": ["all_season"],
                "source_url": SOURCE_URL,
                "source_type": "original_publisher",
                "source_checked_at": CHECKED_AT,
                "nutrition_source_url": None,
                "nutrition_basis": "沿用旧规则宽区间，待按正式菜单或原料成分复核",
                "review_status": "draft",
                "reviewed_by": None,
                "reviewed_at": None,
                "review_notes": "B0 自动映射；上线前必须完成来源、连续性与营养边界审核",
                "is_active": True,
                "catalog_version": 1,
                "taxonomy_version": 1,
                "forbidden_tags": sorted(candidate.forbidden_tags),
                "energy_kcal_min_per_person": candidate.energy_min,
                "energy_kcal_max_per_person": candidate.energy_max,
                "nutrition_note": candidate.nutrition_note,
                "order_tips": [],
                "high_protein": candidate.high_protein,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = build_seed()
    args.output.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"external_seed_b0_ok rows={len(rows)} status=draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
