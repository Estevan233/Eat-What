"""Add the audited home and external candidate catalog structures."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260831_08"
down_revision: str | None = "20260828_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOOD_COLUMNS: tuple[sa.Column[object], ...] = (
    sa.Column("_openid", sa.String(length=64), nullable=False, server_default=""),
    sa.Column("catalog_key", sa.String(length=96), nullable=True),
    sa.Column("aliases_json", sa.JSON(), nullable=True),
    sa.Column("meal_family", sa.String(length=32), nullable=True),
    sa.Column("sub_family", sa.String(length=48), nullable=True),
    sa.Column("cuisine_region", sa.String(length=48), nullable=True),
    sa.Column("staple_type", sa.String(length=32), nullable=True),
    sa.Column("protein_types_json", sa.JSON(), nullable=True),
    sa.Column("serving_style", sa.String(length=16), nullable=True),
    sa.Column("meal_periods_json", sa.JSON(), nullable=True),
    sa.Column("delivery_fit", sa.String(length=24), nullable=True),
    sa.Column("price_band", sa.String(length=16), nullable=True),
    sa.Column("source_url", sa.String(length=512), nullable=True),
    sa.Column("source_type", sa.String(length=32), nullable=True),
    sa.Column("source_checked_at", sa.DateTime(), nullable=True),
    sa.Column("review_status", sa.String(length=24), nullable=False, server_default="draft"),
    sa.Column("reviewed_by", sa.String(length=64), nullable=True),
    sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    sa.Column("review_notes", sa.Text(), nullable=True),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("catalog_version", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("taxonomy_version", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("nutrition_source_url", sa.String(length=512), nullable=True),
    sa.Column("nutrition_basis", sa.String(length=512), nullable=True),
)


def upgrade() -> None:
    for column in FOOD_COLUMNS:
        op.add_column("foods", column)
    op.create_index("ix_foods_openid", "foods", ["_openid"], unique=False)
    op.create_index("ix_foods_catalog_key", "foods", ["catalog_key"], unique=True)
    op.create_index("ix_foods_review_active", "foods", ["review_status", "is_active"])
    op.create_index("ix_foods_catalog_family", "foods", ["meal_family", "sub_family"])
    op.create_index("ix_foods_cuisine_region", "foods", ["cuisine_region"])
    op.create_index("ix_foods_serving_style", "foods", ["serving_style"])

    op.create_table(
        "external_dining_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("_openid", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("catalog_key", sa.String(length=96), nullable=False),
        sa.Column("legacy_key", sa.String(length=64), nullable=True),
        sa.Column("dish_name", sa.String(length=96), nullable=False),
        sa.Column("aliases_json", sa.JSON(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("meal_family", sa.String(length=32), nullable=False),
        sa.Column("sub_family", sa.String(length=48), nullable=False),
        sa.Column("cuisine_region", sa.String(length=48), nullable=False),
        sa.Column("staple_type", sa.String(length=32), nullable=False),
        sa.Column("protein_types_json", sa.JSON(), nullable=True),
        sa.Column("serving_style", sa.String(length=16), nullable=False),
        sa.Column("meal_periods_json", sa.JSON(), nullable=True),
        sa.Column("delivery_fit", sa.String(length=24), nullable=False),
        sa.Column("price_band", sa.String(length=16), nullable=False),
        sa.Column("nature", sa.String(length=16), nullable=False),
        sa.Column("seasonal_solar_terms_json", sa.JSON(), nullable=True),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_checked_at", sa.DateTime(), nullable=False),
        sa.Column("nutrition_source_url", sa.String(length=512), nullable=True),
        sa.Column("nutrition_basis", sa.String(length=512), nullable=True),
        sa.Column("review_status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("catalog_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("taxonomy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("forbidden_tags_json", sa.JSON(), nullable=True),
        sa.Column("energy_kcal_min_per_person", sa.Integer(), nullable=True),
        sa.Column("energy_kcal_max_per_person", sa.Integer(), nullable=True),
        sa.Column("nutrition_note", sa.Text(), nullable=True),
        sa.Column("order_tips_json", sa.JSON(), nullable=True),
        sa.Column("high_protein", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_dining_candidates_catalog_key", "external_dining_candidates", ["catalog_key"], unique=True)
    op.create_index("ix_external_dining_candidates_openid", "external_dining_candidates", ["_openid"])
    op.create_index("ix_external_dining_candidates_legacy_key", "external_dining_candidates", ["legacy_key"], unique=True)
    op.create_index("ix_external_dining_candidates_dish_name", "external_dining_candidates", ["dish_name"])
    op.create_index("ix_external_dining_candidates_review_active", "external_dining_candidates", ["review_status", "is_active"])
    op.create_index("ix_external_dining_candidates_family", "external_dining_candidates", ["meal_family", "sub_family"])
    op.create_index("ix_external_dining_candidates_serving_style", "external_dining_candidates", ["serving_style"])


def downgrade() -> None:
    op.drop_table("external_dining_candidates")
    op.drop_index("ix_foods_openid", table_name="foods")
    op.drop_index("ix_foods_serving_style", table_name="foods")
    op.drop_index("ix_foods_cuisine_region", table_name="foods")
    op.drop_index("ix_foods_catalog_family", table_name="foods")
    op.drop_index("ix_foods_review_active", table_name="foods")
    op.drop_index("ix_foods_catalog_key", table_name="foods")
    for column in reversed(FOOD_COLUMNS):
        op.drop_column("foods", column.name)
