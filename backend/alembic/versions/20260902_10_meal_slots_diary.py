"""Meal-slot diary: three meals per day + manual logs + custom favorites.

- daily_logs: +meal_slot/source/shop_name/note; drop (user_id, log_date) unique
  constraint; add composite index (user_id, log_date, meal_slot, source).
  Uniqueness is enforced at application level (recommendation upsert, manual append).
- recommendation_events: +meal_slot (which meal this recommendation is for)
- favorites: food_id becomes nullable (custom favorites); +custom_name/note;
  add (user_id, custom_name) unique constraint.

copy_from table definitions are supplied so SQLite offline (--sql) compilation
can rebuild tables without reflection (batch constraints require it).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260902_10"
down_revision: str | None = "20260831_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# daily_logs 表在本次迁移执行时刻的结构（upgrade 用）
_daily_logs_before = sa.Table(
    "daily_logs",
    sa.MetaData(),
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("user_id", sa.Integer(), nullable=False),
    sa.Column("log_date", sa.Date(), nullable=False),
    sa.Column("recommendation_event_id", sa.Integer(), nullable=True),
    sa.Column("recommended_food_ids_json", sa.JSON(), nullable=False),
    sa.Column("chosen_food_ids_json", sa.JSON(), nullable=False),
    sa.Column("recommended_meal_json", sa.JSON(), nullable=True),
    sa.Column("chosen_meal_json", sa.JSON(), nullable=True),
    sa.Column("chosen_total_nutrition_json", sa.JSON(), nullable=True),
    sa.Column("mood", sa.String(length=16), nullable=False),
    sa.Column("activity_level", sa.String(length=8), nullable=False),
    sa.Column("weather_tag", sa.String(length=16), nullable=True),
    sa.Column("dining_mode", sa.String(length=16), nullable=False),
    sa.Column("audience", sa.String(length=16), nullable=False),
    sa.Column("party_size", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sa.Column("updated_at", sa.DateTime(), nullable=False),
    sa.UniqueConstraint("user_id", "log_date", name="uq_daily_logs_user_date"),
)

# daily_logs 表在本次迁移完成后的结构（downgrade 重建用）
_daily_logs_after = sa.Table(
    "daily_logs",
    sa.MetaData(),
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("user_id", sa.Integer(), nullable=False),
    sa.Column("log_date", sa.Date(), nullable=False),
    sa.Column("meal_slot", sa.String(length=16), nullable=False),
    sa.Column("source", sa.String(length=16), nullable=False),
    sa.Column("shop_name", sa.String(length=80), nullable=True),
    sa.Column("note", sa.String(length=500), nullable=True),
    sa.Column("recommendation_event_id", sa.Integer(), nullable=True),
    sa.Column("recommended_food_ids_json", sa.JSON(), nullable=False),
    sa.Column("chosen_food_ids_json", sa.JSON(), nullable=False),
    sa.Column("recommended_meal_json", sa.JSON(), nullable=True),
    sa.Column("chosen_meal_json", sa.JSON(), nullable=True),
    sa.Column("chosen_total_nutrition_json", sa.JSON(), nullable=True),
    sa.Column("mood", sa.String(length=16), nullable=False),
    sa.Column("activity_level", sa.String(length=8), nullable=False),
    sa.Column("weather_tag", sa.String(length=16), nullable=True),
    sa.Column("dining_mode", sa.String(length=16), nullable=False),
    sa.Column("audience", sa.String(length=16), nullable=False),
    sa.Column("party_size", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sa.Column("updated_at", sa.DateTime(), nullable=False),
    sa.Index("ix_daily_logs_user_date_slot_source", "user_id", "log_date", "meal_slot", "source"),
)

# favorites 表在本次迁移执行时刻的结构
_favorites_before = sa.Table(
    "favorites",
    sa.MetaData(),
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("user_id", sa.Integer(), nullable=False),
    sa.Column("food_id", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sa.UniqueConstraint("user_id", "food_id", name="uq_favorites_user_food"),
)

# favorites 表在本次迁移完成后的结构（downgrade 重建用）
_favorites_after = sa.Table(
    "favorites",
    sa.MetaData(),
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("user_id", sa.Integer(), nullable=False),
    sa.Column("food_id", sa.Integer(), nullable=True),
    sa.Column("custom_name", sa.String(length=80), nullable=True),
    sa.Column("note", sa.String(length=500), nullable=True),
    sa.Column("created_at", sa.DateTime(), nullable=False),
    sa.UniqueConstraint("user_id", "food_id", name="uq_favorites_user_food"),
    sa.UniqueConstraint("user_id", "custom_name", name="uq_favorites_user_custom"),
)


def upgrade() -> None:
    with op.batch_alter_table("daily_logs", copy_from=_daily_logs_before) as batch_op:
        batch_op.add_column(
            sa.Column("meal_slot", sa.String(length=16), server_default="dinner", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "source", sa.String(length=16), server_default="recommendation", nullable=False
            )
        )
        batch_op.add_column(sa.Column("shop_name", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("note", sa.String(length=500), nullable=True))
        batch_op.drop_constraint("uq_daily_logs_user_date", type_="unique")
        batch_op.create_index(
            "ix_daily_logs_user_date_slot_source",
            ["user_id", "log_date", "meal_slot", "source"],
        )

    with op.batch_alter_table("recommendation_events") as batch_op:
        batch_op.add_column(
            sa.Column("meal_slot", sa.String(length=16), server_default="lunch", nullable=False)
        )

    with op.batch_alter_table("favorites", copy_from=_favorites_before) as batch_op:
        batch_op.alter_column("food_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("custom_name", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("note", sa.String(length=500), nullable=True))
        batch_op.create_unique_constraint("uq_favorites_user_custom", ["user_id", "custom_name"])


def downgrade() -> None:
    with op.batch_alter_table("favorites", copy_from=_favorites_after) as batch_op:
        batch_op.drop_constraint("uq_favorites_user_custom", type_="unique")
        batch_op.drop_column("note")
        batch_op.drop_column("custom_name")
        # 仅当没有 NULL food_id 行时才能恢复 NOT NULL
        batch_op.alter_column("food_id", existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table("recommendation_events") as batch_op:
        batch_op.drop_column("meal_slot")

    with op.batch_alter_table("daily_logs", copy_from=_daily_logs_after) as batch_op:
        batch_op.drop_index("ix_daily_logs_user_date_slot_source")
        batch_op.create_unique_constraint("uq_daily_logs_user_date", ["user_id", "log_date"])
        batch_op.drop_column("note")
        batch_op.drop_column("shop_name")
        batch_op.drop_column("source")
        batch_op.drop_column("meal_slot")
