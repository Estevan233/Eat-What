"""Create private shop+dish dining memories."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260817_05"
down_revision: str | None = "20260817_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dining_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("shop_name", sa.String(length=80), nullable=False),
        sa.Column("dish_name", sa.String(length=80), nullable=False),
        sa.Column("normalized_shop_name", sa.String(length=80), nullable=False),
        sa.Column("normalized_dish_name", sa.String(length=80), nullable=False),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "normalized_shop_name",
            "normalized_dish_name",
            name="uq_dining_memories_user_shop_dish",
        ),
    )
    op.create_index("ix_dining_memories_user_id", "dining_memories", ["user_id"])
    op.create_index("ix_dining_memories_verdict", "dining_memories", ["verdict"])


def downgrade() -> None:
    op.drop_index("ix_dining_memories_verdict", table_name="dining_memories")
    op.drop_index("ix_dining_memories_user_id", table_name="dining_memories")
    op.drop_table("dining_memories")
