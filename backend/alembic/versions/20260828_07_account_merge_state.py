"""Add account identity and merge state to users."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260828_07"
down_revision: str | None = "20260820_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACCOUNT_KIND_STATUS_INDEX = "ix_users_account_kind_status"
MERGED_INTO_INDEX = "ix_users_merged_into_user_id"
MERGED_INTO_FOREIGN_KEY = "fk_users_merged_into_user_id_users"


def _add_common_columns() -> None:
    op.add_column(
        "users",
        sa.Column(
            "account_kind",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'wechat'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "account_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("merged_into_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("merge_started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("merged_at", sa.DateTime(), nullable=True),
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        _add_common_columns()
        op.create_foreign_key(
            MERGED_INTO_FOREIGN_KEY,
            "users",
            "users",
            ["merged_into_user_id"],
            ["id"],
        )
    else:
        op.add_column(
            "users",
            sa.Column(
                "account_kind",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'wechat'"),
            ),
        )
        op.add_column(
            "users",
            sa.Column(
                "account_status",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'active'"),
            ),
        )
        op.execute(
            sa.text(
                "ALTER TABLE users ADD COLUMN merged_into_user_id INTEGER "
                f"CONSTRAINT {MERGED_INTO_FOREIGN_KEY} REFERENCES users (id)"
            )
        )
        op.add_column(
            "users",
            sa.Column("merge_started_at", sa.DateTime(), nullable=True),
        )
        op.add_column(
            "users",
            sa.Column("merged_at", sa.DateTime(), nullable=True),
        )

    op.execute(
        sa.text(
            "UPDATE users SET account_kind = 'guest' "
            "WHERE openid LIKE 'guest:%'"
        )
    )
    op.create_index(
        ACCOUNT_KIND_STATUS_INDEX,
        "users",
        ["account_kind", "account_status"],
        unique=False,
    )
    op.create_index(
        MERGED_INTO_INDEX,
        "users",
        ["merged_into_user_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.drop_constraint(
            MERGED_INTO_FOREIGN_KEY,
            "users",
            type_="foreignkey",
        )

    op.drop_index(MERGED_INTO_INDEX, table_name="users")
    op.drop_index(ACCOUNT_KIND_STATUS_INDEX, table_name="users")

    if bind.dialect.name == "mysql":
        op.drop_column("users", "merged_at")
        op.drop_column("users", "merge_started_at")
        op.drop_column("users", "merged_into_user_id")
        op.drop_column("users", "account_status")
        op.drop_column("users", "account_kind")
        return

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("merged_at")
        batch_op.drop_column("merge_started_at")
        batch_op.drop_column("merged_into_user_id")
        batch_op.drop_column("account_status")
        batch_op.drop_column("account_kind")
