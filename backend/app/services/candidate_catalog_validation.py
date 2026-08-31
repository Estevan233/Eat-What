"""Shared, deterministic validation for source-backed candidate catalog rows."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

CandidateKind = Literal["home", "external"]
SOLAR_TERMS = frozenset(
    {
        "lichun", "yushui", "jingzhe", "chunfen", "qingming", "guyu",
        "lixia", "xiaoman", "mangzhong", "xiazhi", "xiaoshu", "dashu",
        "liqiu", "chushu", "bailu", "qiufen", "hanlu", "shuangjiang",
        "lidong", "xiaoxue", "daxue", "dongzhi", "xiaohan", "dahan",
        "all_season",
    }
)
_PUNCTUATION = re.compile(r"[\s·•・,，。.!！?？、+＋/／()（）\[\]【】_-]+")
_WEAK_VARIANT_WORDS = re.compile(r"(?:少油版|低脂版|健康版|招牌|配青菜|加青菜)")


@dataclass(frozen=True)
class CatalogIssue:
    code: str
    field: str
    message: str


@dataclass(frozen=True)
class CatalogTaxonomy:
    version: int
    meal_families: dict[str, frozenset[str]]
    cuisine_regions: frozenset[str]
    staple_types: frozenset[str]
    protein_types: frozenset[str]
    serving_styles: frozenset[str]
    meal_periods: frozenset[str]
    delivery_fits: frozenset[str]
    price_bands: frozenset[str]
    natures: frozenset[str]
    review_statuses: frozenset[str]
    source_types: frozenset[str]


def _string_sequence(raw: object, *, label: str) -> list[str]:
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ValueError(f"taxonomy {label} must be a string list")
    return raw


def load_taxonomy(path: Path) -> CatalogTaxonomy:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("taxonomy must be an object")
    version = raw.get("taxonomy_version")
    families = raw.get("meal_families")
    if not isinstance(version, int) or not isinstance(families, dict):
        raise ValueError("taxonomy version and meal_families are required")
    meal_families: dict[str, frozenset[str]] = {}
    for family, values in families.items():
        if not isinstance(family, str):
            raise ValueError("meal family key must be a string")
        meal_families[family] = frozenset(_string_sequence(values, label=family))
    return CatalogTaxonomy(
        version=version,
        meal_families=meal_families,
        cuisine_regions=frozenset(_string_sequence(raw.get("cuisine_regions"), label="cuisine_regions")),
        staple_types=frozenset(_string_sequence(raw.get("staple_types"), label="staple_types")),
        protein_types=frozenset(_string_sequence(raw.get("protein_types"), label="protein_types")),
        serving_styles=frozenset(_string_sequence(raw.get("serving_styles"), label="serving_styles")),
        meal_periods=frozenset(_string_sequence(raw.get("meal_periods"), label="meal_periods")),
        delivery_fits=frozenset(_string_sequence(raw.get("delivery_fits"), label="delivery_fits")),
        price_bands=frozenset(_string_sequence(raw.get("price_bands"), label="price_bands")),
        natures=frozenset(_string_sequence(raw.get("natures"), label="natures")),
        review_statuses=frozenset(_string_sequence(raw.get("review_statuses"), label="review_statuses")),
        source_types=frozenset(_string_sequence(raw.get("source_types"), label="source_types")),
    )


def normalize_candidate_name(value: str) -> str:
    return _PUNCTUATION.sub("", value).casefold()


def weak_variant_fingerprint(value: str) -> str:
    return normalize_candidate_name(_WEAK_VARIANT_WORDS.sub("", value))


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return None
    return value


def _enum_issue(
    item: Mapping[str, object],
    field: str,
    allowed: frozenset[str],
) -> CatalogIssue | None:
    value = item.get(field)
    if not isinstance(value, str) or value not in allowed:
        return CatalogIssue("invalid_enum", field, f"{field} must be one of {sorted(allowed)}")
    return None


def _valid_iso_datetime(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _validate_identity_and_family(
    item: Mapping[str, object],
    taxonomy: CatalogTaxonomy,
    kind: CandidateKind,
) -> list[CatalogIssue]:
    issues: list[CatalogIssue] = []
    expected_prefix = f"{kind}:"
    key = item.get("catalog_key")
    if not isinstance(key, str) or not key.startswith(expected_prefix):
        issues.append(
            CatalogIssue(
                "invalid_key",
                "catalog_key",
                f"catalog_key must start with {expected_prefix}",
            )
        )
    family = item.get("meal_family")
    sub_family = item.get("sub_family")
    if not isinstance(family, str) or family not in taxonomy.meal_families:
        issues.append(CatalogIssue("invalid_enum", "meal_family", "unknown meal_family"))
    elif not isinstance(sub_family, str) or sub_family not in taxonomy.meal_families[family]:
        issues.append(
            CatalogIssue(
                "invalid_enum",
                "sub_family",
                "sub_family does not belong to meal_family",
            )
        )
    return issues


def _validate_audit_fields(item: Mapping[str, object]) -> list[CatalogIssue]:
    """来源核验后必须留下可复核的锚点和连续性分。"""
    issues: list[CatalogIssue] = []
    status = item.get("review_status")
    if status in {"source_verified", "content_reviewed", "approved"}:
        anchor = item.get("anchor_food")
        if not isinstance(anchor, str) or not anchor.strip():
            issues.append(
                CatalogIssue(
                    "missing_audit",
                    "anchor_food",
                    "source_verified 及以上状态必须关联现有 anchor_food",
                )
            )
        score = item.get("continuity_score")
        if (
            not isinstance(score, int)
            or isinstance(score, bool)
            or not 0 <= score <= 100
        ):
            issues.append(
                CatalogIssue(
                    "invalid_audit",
                    "continuity_score",
                    "source_verified 及以上状态必须为 0-100 整数",
                )
            )
    return issues


def _validate_enums(
    item: Mapping[str, object],
    taxonomy: CatalogTaxonomy,
) -> list[CatalogIssue]:
    issues: list[CatalogIssue] = []
    for field, allowed in (
        ("cuisine_region", taxonomy.cuisine_regions),
        ("staple_type", taxonomy.staple_types),
        ("serving_style", taxonomy.serving_styles),
        ("delivery_fit", taxonomy.delivery_fits),
        ("price_band", taxonomy.price_bands),
        ("nature", taxonomy.natures),
        ("review_status", taxonomy.review_statuses),
        ("source_type", taxonomy.source_types),
    ):
        issue = _enum_issue(item, field, allowed)
        if issue is not None:
            issues.append(issue)
    return issues


def _validate_controlled_lists(
    item: Mapping[str, object],
    taxonomy: CatalogTaxonomy,
) -> list[CatalogIssue]:
    issues: list[CatalogIssue] = []
    protein_types = _string_list(item.get("protein_types"))
    if (
        protein_types is None
        or not protein_types
        or not set(protein_types) <= taxonomy.protein_types
    ):
        issues.append(
            CatalogIssue(
                "invalid_list",
                "protein_types",
                "protein_types must be a non-empty controlled list",
            )
        )
    elif ({"none", "unknown"} & set(protein_types)) and len(protein_types) > 1:
        issues.append(
            CatalogIssue(
                "mutually_exclusive",
                "protein_types",
                "none/unknown cannot be mixed",
            )
        )

    meal_periods = _string_list(item.get("meal_periods"))
    if (
        meal_periods is None
        or not meal_periods
        or not set(meal_periods) <= taxonomy.meal_periods
    ):
        issues.append(
            CatalogIssue(
                "invalid_list",
                "meal_periods",
                "meal_periods must be a non-empty controlled list",
            )
        )
    elif "any" in meal_periods and len(meal_periods) > 1:
        issues.append(
            CatalogIssue("mutually_exclusive", "meal_periods", "any cannot be mixed")
        )

    solar_terms = _string_list(item.get("seasonal_solar_terms"))
    if solar_terms is None or not solar_terms or not set(solar_terms) <= SOLAR_TERMS:
        issues.append(
            CatalogIssue(
                "invalid_list",
                "seasonal_solar_terms",
                "seasonal_solar_terms must be non-empty and controlled",
            )
        )
    elif "all_season" in solar_terms and len(solar_terms) > 1:
        issues.append(
            CatalogIssue(
                "mutually_exclusive",
                "seasonal_solar_terms",
                "all_season cannot be mixed",
            )
        )
    return issues


def _validate_source_and_versions(
    item: Mapping[str, object],
    taxonomy: CatalogTaxonomy,
) -> list[CatalogIssue]:
    issues: list[CatalogIssue] = []
    source_url = item.get("source_url")
    parsed = urlparse(source_url) if isinstance(source_url, str) else None
    if parsed is None or parsed.scheme != "https" or not parsed.netloc:
        issues.append(
            CatalogIssue(
                "invalid_url",
                "source_url",
                "source_url must be an absolute HTTPS URL",
            )
        )
    if not _valid_iso_datetime(item.get("source_checked_at")):
        issues.append(
            CatalogIssue(
                "invalid_datetime",
                "source_checked_at",
                "source_checked_at must be ISO 8601",
            )
        )
    for field in ("catalog_version", "taxonomy_version"):
        value = item.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            issues.append(
                CatalogIssue(
                    "invalid_version",
                    field,
                    f"{field} must be a positive integer",
                )
            )
    if item.get("taxonomy_version") != taxonomy.version:
        issues.append(
            CatalogIssue(
                "taxonomy_mismatch",
                "taxonomy_version",
                "taxonomy_version does not match registry",
            )
        )
    return issues


def _validate_review_state(item: Mapping[str, object]) -> list[CatalogIssue]:
    issues: list[CatalogIssue] = []
    status = item.get("review_status")
    if status in {"content_reviewed", "approved", "rejected", "retired"}:
        if not isinstance(item.get("reviewed_by"), str) or not item.get("reviewed_by"):
            issues.append(
                CatalogIssue(
                    "missing_review",
                    "reviewed_by",
                    "reviewed_by is required for final review states",
                )
            )
        if not _valid_iso_datetime(item.get("reviewed_at")):
            issues.append(
                CatalogIssue(
                    "missing_review",
                    "reviewed_at",
                    "reviewed_at is required for final review states",
                )
            )
    if not isinstance(item.get("is_active"), bool):
        issues.append(
            CatalogIssue("invalid_boolean", "is_active", "is_active must be boolean")
        )
    elif status == "retired" and item["is_active"] is not False:
        issues.append(
            CatalogIssue(
                "retired_active",
                "is_active",
                "retired candidates must be inactive",
            )
        )
    return issues


def validate_common_candidate(
    item: Mapping[str, object],
    taxonomy: CatalogTaxonomy,
    *,
    kind: CandidateKind,
) -> list[CatalogIssue]:
    return [
        *_validate_identity_and_family(item, taxonomy, kind),
        *_validate_enums(item, taxonomy),
        *_validate_controlled_lists(item, taxonomy),
        *_validate_source_and_versions(item, taxonomy),
        *_validate_review_state(item),
        *_validate_audit_fields(item),
    ]
