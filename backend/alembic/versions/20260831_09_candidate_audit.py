"""Add source-audit anchor and continuity fields to external candidates."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_09"
down_revision: str | None = "20260831_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "external_dining_candidates",
        sa.Column("anchor_food", sa.String(length=96), nullable=True),
    )
    op.add_column(
        "external_dining_candidates",
        sa.Column("continuity_score", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_dining_candidates", "continuity_score")
    op.drop_column("external_dining_candidates", "anchor_food")
