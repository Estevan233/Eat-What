"""Persist dining mode, audience, and party size."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260817_04"
down_revision: str | None = "20260812_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_context_columns(table_name: str) -> None:
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(
            sa.Column("dining_mode", sa.String(length=16), server_default="cook", nullable=False)
        )
        batch_op.add_column(
            sa.Column("audience", sa.String(length=16), server_default="personal", nullable=False)
        )
        batch_op.add_column(
            sa.Column("party_size", sa.Integer(), server_default="1", nullable=False)
        )


def upgrade() -> None:
    _add_context_columns("recommendation_events")
    _add_context_columns("daily_logs")


def _drop_context_columns(table_name: str) -> None:
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_column("party_size")
        batch_op.drop_column("audience")
        batch_op.drop_column("dining_mode")


def downgrade() -> None:
    _drop_context_columns("daily_logs")
    _drop_context_columns("recommendation_events")
