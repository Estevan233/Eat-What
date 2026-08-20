"""Add an idempotency key to recommendation events."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_06"
down_revision: str | None = "20260817_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.add_column(
            "recommendation_events",
            sa.Column("request_id", sa.String(length=64), nullable=True),
        )
        op.execute(
            sa.text(
                "UPDATE recommendation_events "
                "SET request_id = CONCAT('legacy-', id) "
                "WHERE request_id IS NULL"
            )
        )
        op.alter_column(
            "recommendation_events",
            "request_id",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        op.create_index(
            "uq_recommendation_events_request_id",
            "recommendation_events",
            ["request_id"],
            unique=True,
        )
        return

    with op.batch_alter_table("recommendation_events") as batch_op:
        batch_op.add_column(
            sa.Column("request_id", sa.String(length=64), nullable=True)
        )
    op.execute(
        sa.text(
            "UPDATE recommendation_events "
            "SET request_id = 'legacy-' || CAST(id AS TEXT) "
            "WHERE request_id IS NULL"
        )
    )
    with op.batch_alter_table("recommendation_events") as batch_op:
        batch_op.alter_column(
            "request_id",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_index(
            "uq_recommendation_events_request_id",
            ["request_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.drop_index(
            "uq_recommendation_events_request_id",
            table_name="recommendation_events",
        )
        op.drop_column("recommendation_events", "request_id")
        return

    with op.batch_alter_table("recommendation_events") as batch_op:
        batch_op.drop_index("uq_recommendation_events_request_id")
        batch_op.drop_column("request_id")
