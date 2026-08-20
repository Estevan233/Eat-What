"""Create the existing Eat What schema for CloudBase deployment."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '20260812_01'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'foods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('ingredients_json', sa.JSON(), nullable=True),
        sa.Column('calories_kcal_per_100g', sa.Float(), nullable=True),
        sa.Column('nutrition_json', sa.JSON(), nullable=True),
        sa.Column('nature', sa.String(length=16), nullable=False),
        sa.Column('flavor_json', sa.JSON(), nullable=True),
        sa.Column('organ_meridians_json', sa.JSON(), nullable=True),
        sa.Column('suitable_constitutions_json', sa.JSON(), nullable=True),
        sa.Column('suitable_weathers_json', sa.JSON(), nullable=True),
        sa.Column('forbidden_for_json', sa.JSON(), nullable=True),
        sa.Column('tags_json', sa.JSON(), nullable=True),
        sa.Column('cooking_method', sa.String(length=32), nullable=False),
        sa.Column('cooking_time_min', sa.Integer(), nullable=True),
        sa.Column('image_url', sa.String(length=512), nullable=True),
        sa.Column('seasonal_solar_terms_json', sa.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_foods_category', 'foods', ['category'], unique=False)
    op.create_index('ix_foods_cooking_method', 'foods', ['cooking_method'], unique=False)
    op.create_index('ix_foods_name', 'foods', ['name'], unique=True)
    op.create_index('ix_foods_nature', 'foods', ['nature'], unique=False)

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('openid', sa.String(length=64), nullable=False),
        sa.Column('unionid', sa.String(length=64), nullable=True),
        sa.Column('nickname', sa.String(length=64), nullable=False),
        sa.Column('avatar_url', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_openid', 'users', ['openid'], unique=True)

    op.create_table(
        'daily_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('log_date', sa.Date(), nullable=False),
        sa.Column('recommended_food_ids_json', sa.JSON(), nullable=True),
        sa.Column('chosen_food_ids_json', sa.JSON(), nullable=True),
        sa.Column('mood', sa.String(length=16), nullable=False),
        sa.Column('activity_level', sa.String(length=8), nullable=False),
        sa.Column('weather_tag', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'log_date', name='uq_daily_logs_user_date'),
    )
    op.create_index('ix_daily_logs_log_date', 'daily_logs', ['log_date'], unique=False)
    op.create_index('ix_daily_logs_user_id', 'daily_logs', ['user_id'], unique=False)

    op.create_table(
        'favorites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('food_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['food_id'], ['foods.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'food_id', name='uq_favorites_user_food'),
    )
    op.create_index('ix_favorites_food_id', 'favorites', ['food_id'], unique=False)
    op.create_index('ix_favorites_user_id', 'favorites', ['user_id'], unique=False)

    op.create_table(
        'recommendation_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('recommended_food_ids_json', sa.JSON(), nullable=True),
        sa.Column('mood', sa.String(length=16), nullable=False),
        sa.Column('activity_level', sa.String(length=8), nullable=False),
        sa.Column('weather_tag', sa.String(length=16), nullable=True),
        sa.Column('engine', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_recommendation_events_event_date',
        'recommendation_events',
        ['event_date'],
        unique=False,
    )
    op.create_index(
        'ix_recommendation_events_user_date',
        'recommendation_events',
        ['user_id', 'event_date'],
        unique=False,
    )
    op.create_index(
        'ix_recommendation_events_user_id',
        'recommendation_events',
        ['user_id'],
        unique=False,
    )

    op.create_table(
        'user_profiles',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('birthday', sa.String(length=10), nullable=False),
        sa.Column('gender', sa.String(length=8), nullable=False),
        sa.Column('height_cm', sa.Integer(), nullable=True),
        sa.Column('weight_kg', sa.Float(), nullable=True),
        sa.Column('forbidden_tags', sa.JSON(), nullable=True),
        sa.Column('constitution_type', sa.String(length=64), nullable=True),
        sa.Column('constitution_scores', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id'),
    )


def downgrade() -> None:
    op.drop_table('user_profiles')
    op.drop_index('ix_recommendation_events_user_id', table_name='recommendation_events')
    op.drop_index('ix_recommendation_events_user_date', table_name='recommendation_events')
    op.drop_index('ix_recommendation_events_event_date', table_name='recommendation_events')
    op.drop_table('recommendation_events')
    op.drop_index('ix_favorites_user_id', table_name='favorites')
    op.drop_index('ix_favorites_food_id', table_name='favorites')
    op.drop_table('favorites')
    op.drop_index('ix_daily_logs_user_id', table_name='daily_logs')
    op.drop_index('ix_daily_logs_log_date', table_name='daily_logs')
    op.drop_table('daily_logs')
    op.drop_index('ix_users_openid', table_name='users')
    op.drop_table('users')
    op.drop_index('ix_foods_nature', table_name='foods')
    op.drop_index('ix_foods_name', table_name='foods')
    op.drop_index('ix_foods_cooking_method', table_name='foods')
    op.drop_index('ix_foods_category', table_name='foods')
    op.drop_table('foods')
