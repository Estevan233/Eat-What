"""Add meal roles and structured recipes."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '20260812_02'
down_revision: str | None = '20260812_01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('foods') as batch_op:
        batch_op.add_column(sa.Column('meal_role', sa.String(length=16), nullable=True))
        batch_op.add_column(
            sa.Column('recipe_ready', sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(sa.Column('visual_key', sa.String(length=64), nullable=True))
        batch_op.create_index('ix_foods_meal_role', ['meal_role'], unique=False)
        batch_op.create_index('ix_foods_recipe_ready', ['recipe_ready'], unique=False)

    op.create_table(
        'recipes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('food_id', sa.Integer(), nullable=False),
        sa.Column('servings', sa.Integer(), nullable=False),
        sa.Column('ingredients_json', sa.JSON(), nullable=True),
        sa.Column('steps_json', sa.JSON(), nullable=True),
        sa.Column('prep_time_min', sa.Integer(), nullable=False),
        sa.Column('cook_time_min', sa.Integer(), nullable=False),
        sa.Column('nutrition_per_serving_json', sa.JSON(), nullable=True),
        sa.Column('difficulty', sa.String(length=16), nullable=False),
        sa.Column('source_url', sa.String(length=512), nullable=True),
        sa.Column('nutrition_basis', sa.String(length=512), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['food_id'], ['foods.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_recipes_food_id', 'recipes', ['food_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_recipes_food_id', table_name='recipes')
    op.drop_table('recipes')
    with op.batch_alter_table('foods') as batch_op:
        batch_op.drop_index('ix_foods_recipe_ready')
        batch_op.drop_index('ix_foods_meal_role')
        batch_op.drop_column('visual_key')
        batch_op.drop_column('recipe_ready')
        batch_op.drop_column('meal_role')
