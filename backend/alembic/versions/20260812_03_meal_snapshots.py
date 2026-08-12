"""Persist immutable recommendation and chosen meal snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_03"
down_revision: str | None = "20260812_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("recommendation_events") as batch_op:
        batch_op.add_column(sa.Column("primary_food_ids_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("substitution_options_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("primary_meal_json", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("scorer_version", sa.String(length=32), server_default="rules_v2", nullable=False)
        )
        batch_op.add_column(
            sa.Column("builder_version", sa.String(length=32), server_default="legacy", nullable=False)
        )
        batch_op.add_column(sa.Column("agent_name", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("summary_json", sa.JSON(), nullable=True))

    with op.batch_alter_table("daily_logs") as batch_op:
        batch_op.add_column(sa.Column("recommendation_event_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("recommended_meal_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("chosen_meal_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("chosen_total_nutrition_json", sa.JSON(), nullable=True))
        batch_op.create_foreign_key(
            "fk_daily_logs_recommendation_event_id",
            "recommendation_events",
            ["recommendation_event_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_daily_logs_recommendation_event_id",
            ["recommendation_event_id"],
            unique=False,
        )

    # Existing rows retain legacy arrays; empty JSON values keep model defaults valid.
    op.execute(
        sa.text(
            "UPDATE recommendation_events "
            "SET primary_food_ids_json = recommended_food_ids_json "
            "WHERE primary_food_ids_json IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE recommendation_events "
            "SET substitution_options_json = '[]' "
            "WHERE substitution_options_json IS NULL"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("daily_logs") as batch_op:
        batch_op.drop_index("ix_daily_logs_recommendation_event_id")
        batch_op.drop_constraint(
            "fk_daily_logs_recommendation_event_id",
            type_="foreignkey",
        )
        batch_op.drop_column("chosen_total_nutrition_json")
        batch_op.drop_column("chosen_meal_json")
        batch_op.drop_column("recommended_meal_json")
        batch_op.drop_column("recommendation_event_id")

    with op.batch_alter_table("recommendation_events") as batch_op:
        batch_op.drop_column("summary_json")
        batch_op.drop_column("agent_name")
        batch_op.drop_column("builder_version")
        batch_op.drop_column("scorer_version")
        batch_op.drop_column("primary_meal_json")
        batch_op.drop_column("substitution_options_json")
        batch_op.drop_column("primary_food_ids_json")
