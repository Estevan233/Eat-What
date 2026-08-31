from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from scripts.approve_external_dining_seed import REVIEWER, finalize_rows
from scripts.validate_external_dining_seed import validate

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> list[dict[str, object]]:
    raw = json.loads((BACKEND_ROOT / "data" / name).read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    return raw


def test_product_review_finalizes_complete_release_catalog() -> None:
    candidates = _load("external_dining_seed.json")
    foods = _load("food_seed.json")

    rows = finalize_rows(candidates, foods)

    assert len(rows) == 315
    assert len({row["catalog_key"] for row in rows}) == 315
    assert all(row["review_status"] == "approved" for row in rows)
    assert all(row["reviewed_by"] == REVIEWER for row in rows)
    assert all(row.get("anchor_food") for row in rows)
    assert all(isinstance(row.get("continuity_score"), int) for row in rows)
    assert all(row.get("delivery_fit") != "unknown" for row in rows)
    assert not {
        urlparse(str(row["source_url"])).netloc.casefold() for row in rows
    } & {"github.com", "www.ihchina.cn"}
    assert Counter(str(row["serving_style"]) for row in rows) == Counter(
        {"individual": 195, "shared": 105, "either": 15}
    )
    families = Counter(str(row["meal_family"]) for row in rows)
    assert len(families) >= 10
    assert max(families.values()) / len(rows) <= 0.2
    assert validate(rows, allow_draft=False) == []


def test_product_review_is_idempotent() -> None:
    candidates = _load("external_dining_seed.json")
    foods = _load("food_seed.json")

    first = finalize_rows(candidates, foods)
    second = finalize_rows(first, foods)

    assert second == first
