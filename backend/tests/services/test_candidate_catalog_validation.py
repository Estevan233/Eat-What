"""Common candidate-catalog validation contract."""

from copy import deepcopy
from pathlib import Path

from app.services.candidate_catalog_validation import (
    load_taxonomy,
    normalize_candidate_name,
    validate_common_candidate,
    weak_variant_fingerprint,
)
from scripts.validate_candidate_catalog import _cross_catalog_report

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY = load_taxonomy(BACKEND_ROOT / "data" / "candidate_taxonomy_v1.json")


def _valid_external() -> dict[str, object]:
    return {
        "catalog_key": "external:tomato-beef-rice:v1",
        "meal_family": "rice_meal",
        "sub_family": "rice_bowl",
        "cuisine_region": "cn_national",
        "staple_type": "rice",
        "protein_types": ["beef"],
        "serving_style": "individual",
        "meal_periods": ["lunch", "dinner"],
        "delivery_fit": "high",
        "price_band": "standard",
        "nature": "unknown",
        "seasonal_solar_terms": ["all_season"],
        "source_url": "https://example.org/menu/tomato-beef-rice",
        "source_type": "restaurant_menu",
        "source_checked_at": "2026-08-31T10:00:00+08:00",
        "review_status": "source_verified",
        "reviewed_by": None,
        "reviewed_at": None,
        "is_active": True,
        "catalog_version": 1,
        "taxonomy_version": 1,
        "anchor_food": "牛肉面",
        "continuity_score": 80,
    }


def test_valid_candidate_passes_common_contract() -> None:
    assert validate_common_candidate(_valid_external(), TAXONOMY, kind="external") == []


def test_common_contract_reports_source_and_mutual_exclusion_errors() -> None:
    item = deepcopy(_valid_external())
    item.update(
        {
            "source_url": "http://search.example/query",
            "protein_types": ["unknown", "beef"],
            "meal_periods": ["any", "dinner"],
            "seasonal_solar_terms": ["all_season", "dongzhi"],
        }
    )
    issues = validate_common_candidate(item, TAXONOMY, kind="external")
    assert {(issue.code, issue.field) for issue in issues} >= {
        ("invalid_url", "source_url"),
        ("mutually_exclusive", "protein_types"),
        ("mutually_exclusive", "meal_periods"),
        ("mutually_exclusive", "seasonal_solar_terms"),
    }


def test_approved_candidate_requires_reviewer_and_timestamp() -> None:
    item = deepcopy(_valid_external())
    item["review_status"] = "approved"
    issues = validate_common_candidate(item, TAXONOMY, kind="external")
    assert {(issue.code, issue.field) for issue in issues} >= {
        ("missing_review", "reviewed_by"),
        ("missing_review", "reviewed_at"),
    }


def test_source_verified_candidate_requires_audit_anchor_and_score() -> None:
    item = deepcopy(_valid_external())
    item.pop("anchor_food")
    item.pop("continuity_score")
    issues = validate_common_candidate(item, TAXONOMY, kind="external")
    assert {(issue.code, issue.field) for issue in issues} >= {
        ("missing_audit", "anchor_food"),
        ("invalid_audit", "continuity_score"),
    }


def test_retired_candidate_must_be_inactive() -> None:
    item = deepcopy(_valid_external())
    item.update(
        {
            "review_status": "retired",
            "reviewed_by": "reviewer",
            "reviewed_at": "2026-08-31T10:00:00+08:00",
        }
    )
    issues = validate_common_candidate(item, TAXONOMY, kind="external")
    assert ("retired_active", "is_active") in {(issue.code, issue.field) for issue in issues}


def test_name_normalization_exposes_weak_variants() -> None:
    assert normalize_candidate_name("番茄牛腩饭（招牌）") == "番茄牛腩饭招牌"
    assert weak_variant_fingerprint("招牌 番茄牛腩饭 配青菜") == "番茄牛腩饭"


def test_cross_catalog_report_rejects_approved_exact_overlap() -> None:
    errors, summary = _cross_catalog_report(
        [{"name": "番茄鸡蛋饭"}],
        [
            {
                "dish_name": "番茄鸡蛋饭",
                "review_status": "approved",
                "is_active": True,
            }
        ],
    )

    assert errors == ["跨目录 approved 硬重名: 番茄鸡蛋饭"]
    assert summary["exact_name_overlap"] == ["番茄鸡蛋饭"]
