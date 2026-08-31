"""G0 contract for the frozen candidate-catalog baseline and taxonomy."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_PATH = BACKEND_ROOT / "data" / "candidate_taxonomy_v1.json"


def test_baseline_builder_freezes_current_counts(tmp_path: Path) -> None:
    output = tmp_path / "baseline.json"
    env = os.environ.copy()
    env.setdefault("JWT_SECRET", "x" * 32)
    result = subprocess.run(
        [sys.executable, str(BACKEND_ROOT / "scripts" / "build_candidate_baseline.py"), "--output", str(output)],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    baseline = json.loads(output.read_text(encoding="utf-8"))
    assert baseline["food_count"] == 205
    assert baseline["recipe_count"] == 120
    assert baseline["recipe_role_counts"] == {"main": 50, "staple": 20, "vegetable": 50}
    assert baseline["external_rule_count"] == 57
    assert baseline["claim_review_count"] == 38
    assert len(set(baseline["food_names"])) == 205
    assert len(set(baseline["recipe_names"])) == 120
    assert len({item["legacy_key"] for item in baseline["external_rules"]}) == 57


def test_taxonomy_v1_is_internally_consistent() -> None:
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    assert taxonomy["taxonomy_version"] == 1
    sub_families = [value for values in taxonomy["meal_families"].values() for value in values]
    assert len(sub_families) == len(set(sub_families))
    assert sum(taxonomy["external_targets"]["meal_family_counts"].values()) == 315
    assert {
        "individual": taxonomy["external_targets"]["individual"],
        "shared": taxonomy["external_targets"]["shared"],
        "either": taxonomy["external_targets"]["either"],
    } == {"individual": 195, "shared": 105, "either": 15}
    assert sum(taxonomy["continuity_weights"].values()) == 100
    assert set(taxonomy["review_statuses"]) == {"draft", "source_verified", "content_reviewed", "approved", "rejected", "retired"}
