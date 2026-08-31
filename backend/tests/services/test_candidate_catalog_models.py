"""Model and index contract for the additive candidate catalog migration."""

from app.models.external_dining_candidate import ExternalDiningCandidate
from app.models.food import Food


def test_food_declares_additive_catalog_fields() -> None:
    columns = set(Food.__table__.columns.keys())
    assert {
        "catalog_key",
        "_openid",
        "aliases_json",
        "meal_family",
        "sub_family",
        "cuisine_region",
        "staple_type",
        "protein_types_json",
        "serving_style",
        "meal_periods_json",
        "delivery_fit",
        "price_band",
        "source_url",
        "source_type",
        "source_checked_at",
        "review_status",
        "reviewed_by",
        "reviewed_at",
        "review_notes",
        "is_active",
        "catalog_version",
        "taxonomy_version",
        "nutrition_source_url",
        "nutrition_basis",
    } <= columns


def test_food_catalog_json_defaults_are_not_shared() -> None:
    left = Food(name="left", category="other", nature="unknown", cooking_method="other")
    right = Food(name="right", category="other", nature="unknown", cooking_method="other")
    left.aliases_json.append("alias")
    left.protein_types_json.append("soy")
    left.meal_periods_json.append("lunch")
    assert right.aliases_json == []
    assert right.protein_types_json == []
    assert right.meal_periods_json == []


def test_external_candidate_declares_query_and_identity_indexes() -> None:
    table = ExternalDiningCandidate.__table__
    columns = set(table.columns.keys())
    indexes = {index.name for index in table.indexes}
    assert {
        "catalog_key",
        "legacy_key",
        "dish_name",
        "meal_family",
        "sub_family",
        "serving_style",
        "review_status",
        "is_active",
        "forbidden_tags_json",
        "energy_kcal_min_per_person",
        "energy_kcal_max_per_person",
    } <= columns
    assert {
        "ix_external_dining_candidates_catalog_key",
        "ix_external_dining_candidates_openid",
        "ix_external_dining_candidates_review_active",
        "ix_external_dining_candidates_family",
        "ix_external_dining_candidates_serving_style",
    } <= indexes
